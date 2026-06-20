package com.meituan.route;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * AI Local Smart Route Planning System
 * Meituan Hackathon — Track 5
 *
 * Multi-Agent collaborative route planning service.
 * Uses Java 24, Spring Boot 3.4+, WebFlux, LangChain4j, JGraphT.
 */
@SpringBootApplication
public class RouteApplication {

    private static final Logger log = LoggerFactory.getLogger(RouteApplication.class);

    public static void main(String[] args) {
        SpringApplication.run(RouteApplication.class, args);
    }

    @EventListener(ApplicationReadyEvent.class)
    public void onReady() {
        log.info("============================================");
        log.info("  AI Route Planner is ready!");
        log.info("  API: http://localhost:8080/api/route/");
        log.info("  Health: http://localhost:8080/api/route/health");
        log.info("============================================");
    }
}
