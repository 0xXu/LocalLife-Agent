package com.meituan.route.repository;

import com.meituan.route.entity.FavoriteEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface FavoriteRepository extends JpaRepository<FavoriteEntity, Long> {
    List<FavoriteEntity> findAllByOrderByCreatedAtDesc();
    List<FavoriteEntity> findByUserIdOrderByCreatedAtDesc(String userId);
}
