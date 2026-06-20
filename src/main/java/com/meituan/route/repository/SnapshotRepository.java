package com.meituan.route.repository;

import com.meituan.route.entity.SnapshotEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface SnapshotRepository extends JpaRepository<SnapshotEntity, Long> {
    List<SnapshotEntity> findBySessionIdOrderByVersionAsc(String sessionId);
    void deleteBySessionId(String sessionId);
}
