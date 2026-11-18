package org.gdb.semop;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import org.eclipse.rdf4j.query.algebra.evaluation.ValueExprEvaluationException;
import org.eclipse.rdf4j.query.algebra.evaluation.function.Function;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

public abstract class AbstractSemFunction implements Function {

    private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(120);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    protected JsonNode callGateway(String systemPrompt, String userPrompt)
            throws ValueExprEvaluationException {
        try {
            String gatewayURL = resolveGatewayURL();
            String localModel = resolveLocalModel();
            String endpoint = gatewayURL.replaceAll("/+$", "") + "/chat/completions";

            String jsonBody = MAPPER.writeValueAsString(resolveBody(localModel, systemPrompt, userPrompt));

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(endpoint))
                    .timeout(REQUEST_TIMEOUT)
                    .header("Content-Type", "application/json")
                    .header("Authorization", "Bearer " + resolveApiKey())
                    .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                    .build();

            HttpResponse<String> response = HTTP_CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                throw new ValueExprEvaluationException(
                    "Gateway returned HTTP " + response.statusCode() + ": " + response.body()
                );
            }

            JsonNode root = MAPPER.readTree(response.body());
            JsonNode contentNode = root.path("choices").path(0).path("message").path("content");
            if (contentNode.isMissingNode() || !contentNode.isTextual()) {
                throw new ValueExprEvaluationException("Missing message content in LLM response");
            }

            String cleanContent = contentNode.asText().replaceAll("(?m)^```(?:json)?|```$", "").trim();
            return MAPPER.readTree(cleanContent);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ValueExprEvaluationException("HTTP request to gateway interrupted", e);
        } catch (ValueExprEvaluationException e) {
            throw e;
        } catch (Exception e) {
            throw new ValueExprEvaluationException("Error communicating with gateway: " + e.getMessage(), e);
        }
    }

    private ObjectNode resolveBody(String localModel, String systemPrompt, String userPrompt) {
        ObjectNode body = MAPPER.createObjectNode();
        body.put("model", localModel);
        body.put("temperature", 0);
        body.put("seed", 0);
        body.put("max_tokens", 300);
        body.put("stream", false);
        body.putObject("response_format").put("type", "json_object");

        ArrayNode messages = body.putArray("messages");
        messages.addObject().put("role", "system").put("content", systemPrompt);
        messages.addObject().put("role", "user").put("content", userPrompt);

        return body;
    }

    private String resolveGatewayURL() throws ValueExprEvaluationException {
        String gatewayURL = System.getenv("GATEWAY_URL");
        if (gatewayURL == null || gatewayURL.isBlank()) {
            throw new ValueExprEvaluationException("Environment variable GATEWAY_URL is not set or empty");
        }
        return gatewayURL.trim();
    }

    private String resolveLocalModel() throws ValueExprEvaluationException {
        String localModel = System.getenv("LOCAL_MODEL");
        if (localModel == null || localModel.isBlank()) {
            throw new ValueExprEvaluationException("Environment variable LOCAL_MODEL is not set or empty");
        }
        return localModel.trim();
    }

    private String resolveApiKey() {
        String key = System.getenv("LOCAL_MODEL_API_KEY");
        return (key == null || key.isBlank()) ? "ollama" : key.trim();
    }
}