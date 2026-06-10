package com.eshop.api.exception;

public class ChatAgentUnavailableException extends ApiException {

    public ChatAgentUnavailableException(String message) {
        super(message, 503);
    }

    public ChatAgentUnavailableException(String message, Throwable cause) {
        super(message, 503, cause);
    }
}
