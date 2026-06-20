package com.meituan.route;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.meituan.route.entity.FavoriteEntity;
import com.meituan.route.model.Route;
import com.meituan.route.repository.FavoriteRepository;
import com.meituan.route.service.UserProfileService;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/favorites")
public class FavoriteController {

    private final FavoriteRepository favoriteRepository;
    private final UserProfileService userProfileService;
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public FavoriteController(FavoriteRepository favoriteRepository, UserProfileService userProfileService) {
        this.favoriteRepository = favoriteRepository;
        this.userProfileService = userProfileService;
    }

    /**
     * POST /api/favorites — Save a route to favorites (user-scoped).
     * Also updates the user's preference profile based on favorited POI tags.
     */
    @PostMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<FavoriteEntity> save(@RequestBody SaveRequest request) {
        var entity = new FavoriteEntity();
        entity.setUserId(request.userId());
        entity.setRouteJson(request.routeJson());
        entity.setRouteName(request.routeName());
        entity.setScene(request.scene());
        entity.setPoiCount(request.poiCount() != null ? request.poiCount() : 0);
        entity.setTotalTime(request.totalTime());
        entity.setTotalCost(request.totalCost() != null ? request.totalCost() : 0);
        var saved = favoriteRepository.save(entity);

        // Learn from the favorited route to personalize future recommendations
        if (request.userId() != null && !request.userId().isBlank() && request.routeJson() != null) {
            try {
                var route = MAPPER.readValue(request.routeJson(), Route.class);
                userProfileService.learnFromFavorite(request.userId(), route);
            } catch (JsonProcessingException e) {
                // Non-critical: favorite is saved even if profile update fails
                // Could be old format or partial data
            }
        }

        return Mono.just(saved);
    }

    /**
     * GET /api/favorites?userId=xxx — List favorites for a specific user (newest first).
     * Without userId, returns all (backward compatible).
     */
    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<List<FavoriteEntity>> list(@RequestParam(required = false) String userId) {
        if (userId != null && !userId.isBlank()) {
            return Mono.just(favoriteRepository.findByUserIdOrderByCreatedAtDesc(userId));
        }
        return Mono.just(favoriteRepository.findAllByOrderByCreatedAtDesc());
    }

    /**
     * DELETE /api/favorites/{id}?userId=xxx — Remove a favorite (userId required for ownership check).
     */
    @DeleteMapping(value = "/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<Map<String, Object>> delete(@PathVariable Long id, @RequestParam String userId) {
        if (userId == null || userId.isBlank()) {
            return Mono.just(Map.of("success", false, "message", "userId is required"));
        }
        var opt = favoriteRepository.findById(id);
        if (opt.isEmpty()) {
            return Mono.just(Map.of("success", false, "message", "Favorite not found"));
        }
        var entity = opt.get();
        // Verify ownership: only the owner can delete their favorites
        if (!userId.equals(entity.getUserId())) {
            return Mono.just(Map.of("success", false, "message", "Not authorized to delete this favorite"));
        }
        favoriteRepository.deleteById(id);
        return Mono.just(Map.of("success", true, "id", id));
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record SaveRequest(
            String userId,
            String routeJson,
            String routeName,
            String scene,
            Integer poiCount,
            String totalTime,
            Integer totalCost
    ) {}
}
