package org.gdb.semop;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.ValueFactory;
import org.eclipse.rdf4j.query.algebra.evaluation.ValueExprEvaluationException;
import org.eclipse.rdf4j.query.algebra.evaluation.function.Function;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

public class FilterFunction implements Function {

    private static final HttpClient HTTP_CLIENT = HttpClient.newHttpClient();
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Override
    public String getURI() {
        return "http://example.org/semop/function/filter";
    }

    @Override
    public Value evaluate(ValueFactory valueFactory, Value... args)
            throws ValueExprEvaluationException {

        if (args.length != 3) {
            throw new ValueExprEvaluationException(
                "Filter function expects exactly 3 arguments"
            );
        }

        String tau = args[0].stringValue().trim();
        String criterion = args[1].stringValue().trim();
        String runID = args[2].stringValue().trim();

        if (tau.isBlank()) {
            return valueFactory.createLiteral(false);
        }

        if (criterion.isBlank() || runID.isBlank()) {
            throw new ValueExprEvaluationException(
                "Criterion and runID cannot be null or empty"
            );
        }

        String gatewayURL = resolveGatewayURL();
        String localModel = resolveLocalModel();

        boolean result = queryGateway(gatewayURL, localModel, tau, criterion);
        return valueFactory.createLiteral(result);
    }

    private boolean queryGateway(String gatewayURL, String localModel, String tau, String criterion)
            throws ValueExprEvaluationException {
        try {
            String endpoint = gatewayURL.replaceAll("/+$", "") + "/chat/completions";
            String jsonBody = MAPPER.writeValueAsString(resolveBody(localModel, tau, criterion));

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(endpoint))
                    .header("Content-Type", "application/json")
                    .header("Authorization", "Bearer ollama")
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

            String cleanContent = contentNode.asText()
                    .replaceAll("(?m)^```(?:json)?|```$", "")
                    .trim();

            JsonNode parsedAnswer = MAPPER.readTree(cleanContent);
            JsonNode answerNode = parsedAnswer.get("answer");

            if (answerNode == null || !answerNode.isBoolean()) {
                throw new ValueExprEvaluationException(
                    "Parse failure: expected boolean 'answer' field, got: " + cleanContent
                );
            }

            return answerNode.asBoolean();

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ValueExprEvaluationException("HTTP request to gateway interrupted", e);
        } catch (ValueExprEvaluationException e) {
            throw e;
        } catch (Exception e) {
            throw new ValueExprEvaluationException("Error communicating with gateway: " + e.getMessage(), e);
        }
    }

    private ObjectNode resolveBody(String localModel, String tau, String criterion) {
        ObjectNode body = MAPPER.createObjectNode();
        body.put("model", localModel);
        body.put("temperature", 0);
        body.put("seed", 0);
        body.put("max_tokens", 300);
        body.put("stream", false);
        body.putObject("response_format").put("type", "json_object");

        ArrayNode messages = body.putArray("messages");
        messages.addObject()
                .put("role", "system")
                .put("content", "Respond only with JSON: {\"answer\": true} or {\"answer\": false}.");
        messages.addObject()
                .put("role", "user")
                .put("content", "Criterion: " + criterion + "\nInput: " + tau);

        return body;
    }

    private String resolveGatewayURL() throws ValueExprEvaluationException {
        String gatewayURL = System.getenv("GATEWAY_URL");
        if (gatewayURL == null || gatewayURL.isBlank()) {
            throw new ValueExprEvaluationException(
                "GATEWAY_URL environment variable is not set or empty"
            );
        }
        return gatewayURL.trim();
    }

    private String resolveLocalModel() throws ValueExprEvaluationException {
        String localModel = System.getenv("LOCAL_MODEL");
        if (localModel == null || localModel.isBlank()) {
            throw new ValueExprEvaluationException(
                "LOCAL_MODEL environment variable is not set or empty"
            );
        }
        return localModel.trim();
    }
}