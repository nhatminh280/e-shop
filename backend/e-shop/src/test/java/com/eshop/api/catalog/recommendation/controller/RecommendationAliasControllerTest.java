package com.eshop.api.catalog.recommendation.controller;

import com.eshop.api.catalog.recommendation.service.ProductRecommendationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class RecommendationAliasControllerTest {

    private ProductRecommendationService productRecommendationService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        productRecommendationService = mock(ProductRecommendationService.class);
        mockMvc = MockMvcBuilders
            .standaloneSetup(new RecommendationAliasController(productRecommendationService))
            .build();
    }

    @Test
    void shouldReturnEmptyPersonalizedRecommendationsWithoutCallingRecommendationService() throws Exception {
        mockMvc.perform(get("/api/recommendations/personalized")
                .param("userId", "user-1")
                .param("limit", "4"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.recommendations").isEmpty())
            .andExpect(jsonPath("$.totalResults").value(0));

        verifyNoInteractions(productRecommendationService);
    }
}
