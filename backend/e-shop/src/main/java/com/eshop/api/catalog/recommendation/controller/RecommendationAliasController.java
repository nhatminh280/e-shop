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
}
