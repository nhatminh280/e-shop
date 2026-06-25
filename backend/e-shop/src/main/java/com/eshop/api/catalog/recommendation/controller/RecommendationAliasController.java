package com.eshop.api.catalog.recommendation.controller;

import com.eshop.api.catalog.recommendation.dto.ProductRecommendationResponse;
import com.eshop.api.catalog.recommendation.service.ProductRecommendationService;
import com.eshop.api.exception.InvalidRecommendationRequestException;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/recommendations")
@RequiredArgsConstructor
public class RecommendationAliasController {

    private final ProductRecommendationService productRecommendationService;

    @GetMapping("/similar")
    public ResponseEntity<ProductRecommendationResponse> recommendSimilarProducts(
        @RequestParam(value = "variantId", required = false) UUID variantId,
        @RequestParam(value = "limit", required = false) Integer limit
    ) {
        if (variantId == null) {
            throw new InvalidRecommendationRequestException("Parameter 'variantId' is required");
        }
        ProductRecommendationResponse response = productRecommendationService.getRecommendations(variantId, limit);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/personalized")
    public ResponseEntity<ProductRecommendationResponse> recommendPersonalizedProducts(
        @RequestParam(value = "userId", required = false) String userId,
        @RequestParam(value = "limit", required = false) Integer limit
    ) {
        ProductRecommendationResponse response = ProductRecommendationResponse.builder()
            .recommendations(List.of())
            .responseTimeMs(0.0)
            .fromCache(false)
            .totalResults(0)
            .build();
        return ResponseEntity.ok(response);
    }
}
