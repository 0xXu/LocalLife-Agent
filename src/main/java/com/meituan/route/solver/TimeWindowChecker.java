package com.meituan.route.solver;

import com.meituan.route.model.POI;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.LocalTime;

/**
 * Time window checker for POI operating hours and route timing.
 */
@Component
public class TimeWindowChecker {

    /**
     * Check if POI can be visited within the given time constraint.
     */
    public TimeCheckResult check(POI poi, LocalTime arrival, LocalTime departure) {
        var issues = new java.util.ArrayList<String>();

        boolean openOk = !arrival.isBefore(poi.openTime()) && !departure.isAfter(poi.closeTime());
        if (!openOk) {
            issues.add("POI operates " + poi.openTime() + "-" + poi.closeTime()
                    + ", but requested " + arrival + "-" + departure);
        }

        boolean durationOk = Duration.between(arrival, departure).toMinutes() >= poi.visitDuration();
        if (!durationOk) {
            issues.add("Minimum visit duration is " + poi.visitDuration() + " min");
        }

        return new TimeCheckResult(openOk && durationOk, issues, poi);
    }

    /**
     * Find the earliest feasible arrival time for a POI.
     */
    public LocalTime earliestFeasibleArrival(POI poi, LocalTime earliest) {
        return earliest.isBefore(poi.openTime()) ? poi.openTime() : earliest;
    }

    /**
     * Calculate the effective end time considering POI closing.
     */
    public LocalTime latestFeasibleStart(POI poi, LocalTime latest) {
        return latest.isAfter(poi.closeTime().minusMinutes(poi.visitDuration()))
                ? poi.closeTime().minusMinutes(poi.visitDuration())
                : latest;
    }

    public record TimeCheckResult(boolean feasible, java.util.List<String> issues, POI poi) {}
}
