package com.meituan.route.entity;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "favorites")
public class FavoriteEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "route_json", columnDefinition = "TEXT", nullable = false)
    private String routeJson;

    @Column(name = "route_name", length = 200)
    private String routeName;

    @Column(name = "scene", length = 100)
    private String scene;

    @Column(name = "user_id", length = 50)
    private String userId;

    @Column(name = "poi_count")
    private Integer poiCount = 0;

    @Column(name = "total_time", length = 50)
    private String totalTime;

    @Column(name = "total_cost")
    private Integer totalCost = 0;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public FavoriteEntity() {}

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) createdAt = Instant.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getRouteJson() { return routeJson; }
    public void setRouteJson(String routeJson) { this.routeJson = routeJson; }

    public String getRouteName() { return routeName; }
    public void setRouteName(String routeName) { this.routeName = routeName; }

    public String getScene() { return scene; }
    public void setScene(String scene) { this.scene = scene; }

    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }

    public Integer getPoiCount() { return poiCount; }
    public void setPoiCount(Integer poiCount) { this.poiCount = poiCount; }

    public String getTotalTime() { return totalTime; }
    public void setTotalTime(String totalTime) { this.totalTime = totalTime; }

    public Integer getTotalCost() { return totalCost; }
    public void setTotalCost(Integer totalCost) { this.totalCost = totalCost; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
