package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatNodeTrace;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface ChatNodeTraceRepository extends JpaRepository<ChatNodeTrace, UUID> {
}
