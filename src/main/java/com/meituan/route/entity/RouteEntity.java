package com.meituan.route.entity;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "routes")
public class RouteEntity {

    @Id
    @Column(length = 50)
    private String id;

    @Column(name = "user_id", length = 50)
    private String userId;

    @Column(name = "session_id", nullable = false, length = 50)
    private String sessionId;

    @Column(length = 200)
    private String name;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(name = "segments_json", columnDefinition = "TEXT", nullable = false)
    private String segmentsJson;

    @Column(name = "total_cost")
    private Double totalCost;

    @Column(name = "total_travel_time")
    private Double totalTravelTime;

    @Column(name = "total_rating")
    private Double totalRating;

    @Column(name = "optimization_goal", length = 50)
    private String optimizationGoal;

    private Double score;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public RouteEntity() {}

    public RouteEntity(String id, String sessionId, String name, String description,
                       String segmentsJson, Double totalCost, Double totalTravelTime,
                       Double totalRating, String optimizationGoal, Double score) {
        this.id = id;
        this.sessionId = sessionId;
        this.name = name;
        this.description = description;
        this.segmentsJson = segmentsJson;
        this.totalCost = totalCost;
        this.totalTravelTime = totalTravelTime;
        this.totalRating = totalRating;
        this.optimizationGoal = optimizationGoal;
        this.score = score;
        this.createdAt = Instant.now();
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }
    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getSegmentsJson() { return segmentsJson; }
    public void setSegmentsJson(String segmentsJson) { this.segmentsJson = segmentsJson; }
    public Double getTotalCost() { return totalCost; }
    public void setTotalCost(Double totalCost) { this.totalCost = totalCost; }
    public Double getTotalTravelTime() { return totalTravelTime; }
    public void setTotalTravelTime(Double totalTravelTime) { this.totalTravelTime = totalTravelTime; }
    public Double getTotalRating() { return totalRating; }
    public void setTotalRating(Double totalRating) { this.totalRating = totalRating; }
    public String getOptimizationGoal() { return optimizationGoal; }
    public void setOptimizationGoal(String optimizationGoal) { this.optimizationGoal = optimizationGoal; }
    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
