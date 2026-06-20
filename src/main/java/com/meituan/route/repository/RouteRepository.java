package com.meituan.route.repository;

import com.meituan.route.entity.RouteEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface RouteRepository extends JpaRepository<RouteEntity, String> {
    List<RouteEntity> findBySessionIdOrderByCreatedAtAsc(String sessionId);
}
