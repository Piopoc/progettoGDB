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

        if (args.length < 5) {
            throw new ValueExprEvaluationException(
                "Classify function expects at least 5 arguments"
            );
        }

        String tau = args[0].stringValue().trim();
        String criterion = args[1].stringValue().trim();
        String runID = args[2].stringValue().trim();

        if (tau.isBlank()) {
            return valueFactory.createLiteral("");
        }

        if (criterion.isBlank()) {
            throw new ValueExprEvaluationException("criterion cannot be null or empty");
        }

        if (runID.isBlank()) {
            throw new ValueExprEvaluationException("runID cannot be null or empty");
        }

        List<String> categories = new ArrayList<>();
        for (int i = 3; i < args.length; i++) {
            String cat = args[i].stringValue().trim();
            if (cat.isBlank()) {
                throw new ValueExprEvaluationException(
                    "All arguments after the first three cannot be null or empty"
                );
            }
            categories.add(cat);
        }

        String systemPrompt = "Respond only with JSON: {\"label\": \"<category>\"}, choosing exactly one category from the provided list.";
        String userPrompt = "Criterion: " + criterion + "\nInput: " + tau + "\nCategories: " + String.join(", ", categories);

        JsonNode parsedAnswer = callGateway(systemPrompt, userPrompt);

        String answer = parsedAnswer.path("label").asText().trim();
        if (answer.isBlank()) {
            throw new ValueExprEvaluationException("The LLM response did not contain a valid 'label' field.");
        }

        for (String category : categories) {
            if (category.equalsIgnoreCase(answer)) {
                return valueFactory.createLiteral(category);
            }
        }

        throw new ValueExprEvaluationException("The LLM returned an invalid category: " + answer);
    }
}