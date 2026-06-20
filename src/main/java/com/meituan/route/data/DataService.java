package com.meituan.route.data;

import com.meituan.route.model.POI;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.List;

/**
 * Data service interface for POI retrieval.
 * Two implementations: MockDataService (local JSON) and DianpingApiDataService (real API).
 */
public interface DataService {
    Flux<POI> searchByCategory(String city, String district, String category);
    Flux<POI> searchByKeyword(String city, String district, String keyword);
    Flux<POI> searchWithinBudget(String city, String district, double maxCost);
    Mono<POI> findById(String id);
    Flux<POI> getAllByCity(String city);
    Flux<POI> getByDistrict(String city, String district);
    List<String> getAvailableCities();
    List<String> getAvailableDistricts(String city);
}
