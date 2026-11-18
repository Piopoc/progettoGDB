package org.gdb.semop;

import java.util.ArrayList;
import java.util.List;

import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.ValueFactory;
import org.eclipse.rdf4j.query.algebra.evaluation.ValueExprEvaluationException;

import com.fasterxml.jackson.databind.JsonNode;

public class ClassifyFunction extends AbstractSemFunction {

    @Override
    public String getURI() {
        return "http://example.org/semop/function/classify";
    }

    @Override
    public Value evaluate(ValueFactory valueFactory, Value... args)
            throws ValueExprEvaluationException {

        if (args.length < 4) {
            throw new ValueExprEvaluationException(
                "Classify function expects at least 4 arguments"
            );
        }

        String tau = args[0].stringValue().trim();
        String runID = args[1].stringValue().trim();

        if (tau.isBlank()) {
            return valueFactory.createLiteral("");
        }

        if (runID.isBlank()) {
            throw new ValueExprEvaluationException("runID cannot be null or empty");
        }

        List<String> categories = new ArrayList<>();
        for (int i = 2; i < args.length; i++) {
            String cat = args[i].stringValue().trim();
            if (cat.isBlank()) {
                throw new ValueExprEvaluationException(
                    "All arguments after the first two cannot be null or empty"
                );
            }
            categories.add(cat);
        }

        String systemPrompt = "Respond only with JSON: {\"reasoning\": \"<1 sentence analyzing tone and genre>\", \"answer\": \"<category>\"}, choosing one of the provided list.";
        String userPrompt = "Categories: " + String.join(", ", categories) + "\nInput: " + tau;

        JsonNode parsedAnswer = callGateway(systemPrompt, userPrompt);

        String answer = parsedAnswer.path("answer").asText().trim();
        if (answer.isBlank()) {
            throw new ValueExprEvaluationException("The LLM response did not contain a valid 'answer' field.");
        }

        for (String category : categories) {
            if (category.equalsIgnoreCase(answer)) {
                return valueFactory.createLiteral(category);
            }
        }

        throw new ValueExprEvaluationException("The LLM returned an invalid category: " + answer);
    }
}