package com.meituan.route.repository;

import com.meituan.route.entity.SessionEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface SessionRepository extends JpaRepository<SessionEntity, String> {
    List<SessionEntity> findByUserIdOrderByCreatedAtDesc(String userId);
}
