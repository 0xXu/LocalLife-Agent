package com.meituan.route.state;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.meituan.route.entity.SessionEntity;
import com.meituan.route.entity.SnapshotEntity;
import com.meituan.route.model.Route;
import com.meituan.route.model.UserIntent;
import com.meituan.route.repository.SessionRepository;
import com.meituan.route.repository.SnapshotRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Manages session state for multi-turn conversation.
 * Uses in-memory ConcurrentHashMap with DB persistence as recovery source.
 * Stale sessions (inactive > 30 min) are evicted from memory to prevent leaks.
 */
@Component
public class SessionStateManager {

    private static final Logger log = LoggerFactory.getLogger(SessionStateManager.class);
    private static final Duration SESSION_TTL = Duration.ofMinutes(30);

    private final Map<String, Session> sessions = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper;
    private final AtomicLong lastCleanup = new AtomicLong(0);

    private final SessionRepository sessionRepository;
    private final SnapshotRepository snapshotRepository;

    public SessionStateManager(SessionRepository sessionRepository,
                               SnapshotRepository snapshotRepository) {
        this.sessionRepository = sessionRepository;
        this.snapshotRepository = snapshotRepository;
        this.objectMapper = new ObjectMapper();
        this.objectMapper.registerModule(new JavaTimeModule());
    }

    public String createSession() {
        return createSession(null);
    }

    public String createSession(String userId) {
        String id = "sess_" + UUID.randomUUID().toString().substring(0, 8);
        var now = Instant.now();
        sessions.put(id, new Session(id, userId, new ArrayList<>(), null, now, now));

        try {
            sessionRepository.save(new SessionEntity(id, userId, null, now, now));
        } catch (Exception e) {
            log.warn("Failed to persist session to DB: {}", e.getMessage());
        }
        return id;
    }

    public Optional<Session> getSession(String sessionId) {
        evictStale();
        var session = sessions.get(sessionId);
        if (session != null) return Optional.of(session);

        // Try loading from DB
        try {
            var entity = sessionRepository.findById(sessionId);
            if (entity.isPresent()) {
                var snapshots = loadSnapshots(sessionId);
                var intent = entity.get().getIntentJson() != null
                    ? parseIntent(entity.get().getIntentJson()) : null;
                var restored = new Session(sessionId, entity.get().getUserId(), snapshots, intent,
                    entity.get().getCreatedAt(), entity.get().getUpdatedAt());
                sessions.put(sessionId, restored);
                return Optional.of(restored);
            }
        } catch (Exception e) {
            log.warn("Failed to load session from DB: {}", e.getMessage());
        }
        return Optional.empty();
    }

    public void addSnapshot(String sessionId, Route route, UserIntent intent) {
        addSnapshots(sessionId, List.of(route), intent);
    }

    /**
     * Batch-save multiple route snapshots in a single DB round-trip.
     * Avoids the per-route save loop that puts unnecessary pressure on the connection pool.
     */
    public void addSnapshots(String sessionId, List<Route> routes, UserIntent intent) {
        var session = sessions.get(sessionId);
        if (session == null) return;

        int baseVersion = session.snapshots().size();
        var entities = new ArrayList<SnapshotEntity>();
        var newSnapshots = new ArrayList<>(session.snapshots());

        for (int i = 0; i < routes.size(); i++) {
            int version = baseVersion + i + 1;
            var snapshot = new Snapshot(version, routes.get(i), intent, Instant.now());
            newSnapshots.add(snapshot);
            entities.add(new SnapshotEntity(sessionId, version,
                    toJson(routes.get(i)), intent != null ? toJson(intent) : null));
        }

        var updated = new Session(sessionId, session.userId(), newSnapshots, intent, session.createdAt(), Instant.now());
        sessions.put(sessionId, updated);

        try {
            snapshotRepository.saveAll(entities);
            sessionRepository.save(new SessionEntity(sessionId, session.userId(),
                    intent != null ? toJson(intent) : null,
                    session.createdAt(), Instant.now()));
        } catch (Exception e) {
            log.warn("Failed to persist snapshots to DB: {}", e.getMessage());
        }
    }

    public void updateIntent(String sessionId, UserIntent intent) {
        var session = sessions.get(sessionId);
        if (session != null) {
            sessions.put(sessionId, new Session(sessionId, session.userId(), session.snapshots(), intent,
                    session.createdAt(), Instant.now()));
        }
    }

    public Optional<Route> getLatestRoute(String sessionId) {
        return getSession(sessionId)
                .map(Session::snapshots)
                .filter(s -> !s.isEmpty())
                .map(s -> s.get(s.size() - 1).route());
    }

    public List<Route> getAllRoutes(String sessionId) {
        return getSession(sessionId)
                .map(Session::snapshots)
                .orElse(List.of())
                .stream()
                .map(Snapshot::route)
                .toList();
    }

    public int resolveAdjustment(String adjustment, Route currentRoute) {
        var adj = adjustment.toLowerCase();

        if (adj.contains("前面") || adj.contains("前几家")) {
            if (adj.contains("都不")) return 0;
            if (adj.contains("一家") || adj.contains("一个")) return 1;
            if (adj.contains("两家") || adj.contains("两个")) return 2;
            return 1;
        }

        if (adj.contains("最后") || adj.contains("后面")) {
            if (adj.contains("一家") || adj.contains("一个")) {
                int segCount = currentRoute.segments().size();
                return segCount - 1;
            }
            return 0;
        }

        if (adj.contains("换成") || adj.contains("换")) {
            for (int i = 0; i < currentRoute.segments().size(); i++) {
                var seg = currentRoute.segments().get(i);
                if (adj.contains(seg.poi().name()) || adj.contains(seg.poi().category())) {
                    return i;
                }
            }
            return currentRoute.segments().size() - 1;
        }

        return 0;
    }

    /** Evict stale sessions (inactive > TTL) from memory. Runs at most every 5 min. */
    private void evictStale() {
        var now = System.currentTimeMillis();
        var last = lastCleanup.get();
        if (now - last < Duration.ofMinutes(5).toMillis()) return;
        if (!lastCleanup.compareAndSet(last, now)) return;

        var cutoff = Instant.now().minus(SESSION_TTL);
        var it = sessions.entrySet().iterator();
        int removed = 0;
        while (it.hasNext()) {
            var entry = it.next();
            if (entry.getValue().updatedAt().isBefore(cutoff)) {
                it.remove();
                removed++;
            }
        }
        if (removed > 0) log.info("Evicted {} stale sessions", removed);
    }

    private List<Snapshot> loadSnapshots(String sessionId) {
        try {
            return snapshotRepository.findBySessionIdOrderByVersionAsc(sessionId)
                .stream()
                .map(e -> {
                    try {
                        var route = objectMapper.readValue(e.getRouteJson(), Route.class);
                        var intent = e.getIntentJson() != null
                            ? objectMapper.readValue(e.getIntentJson(), UserIntent.class) : null;
                        return new Snapshot(e.getVersion(), route, intent, e.getCreatedAt());
                    } catch (JsonProcessingException ex) {
                        log.warn("Failed to deserialize snapshot: {}", ex.getMessage());
                        return null;
                    }
                })
                .filter(Objects::nonNull)
                .toList();
        } catch (Exception e) {
            log.warn("Failed to load snapshots from DB: {}", e.getMessage());
            return List.of();
        }
    }

    private String toJson(Object obj) {
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            log.warn("Failed to serialize object: {}", e.getMessage());
            return "{}";
        }
    }

    private UserIntent parseIntent(String json) {
        try {
            return objectMapper.readValue(json, UserIntent.class);
        } catch (JsonProcessingException e) {
            return null;
        }
    }

    public record Session(
            String sessionId,
            String userId,
            List<Snapshot> snapshots,
            UserIntent currentIntent,
            Instant createdAt,
            Instant updatedAt
    ) {}

    public record Snapshot(
            int version,
            Route route,
            UserIntent intent,
            Instant timestamp
    ) {}
}
