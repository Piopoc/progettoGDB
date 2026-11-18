package org.gdb.semop;

import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.ValueFactory;
import org.eclipse.rdf4j.query.algebra.evaluation.ValueExprEvaluationException;

import com.fasterxml.jackson.databind.JsonNode;

public class FilterFunction extends AbstractSemFunction {

    private static final String SYSTEM_PROMPT =
            "Decide whether the input satisfies the criterion. "
            + "Reply only with JSON containing a boolean field named \"answer\".";

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

        String userPrompt = "Criterion: " + criterion + "\nInput: " + tau;
        JsonNode parsedAnswer = callGateway(SYSTEM_PROMPT, userPrompt);
        JsonNode answerNode = parsedAnswer.get("answer");

        if (answerNode == null || !answerNode.isBoolean()) {
            throw new ValueExprEvaluationException(
                "Parse failure: expected boolean 'answer' field, got: " + parsedAnswer
            );
        }

        return valueFactory.createLiteral(answerNode.asBoolean());
    }
}