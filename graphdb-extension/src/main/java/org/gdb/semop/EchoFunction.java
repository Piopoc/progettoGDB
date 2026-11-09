
package org.gdb.semop;

import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.ValueFactory;
import org.eclipse.rdf4j.query.algebra.evaluation.ValueExprEvaluationException;
import org.eclipse.rdf4j.query.algebra.evaluation.function.Function;

public class EchoFunction implements Function {

    @Override
    public String getURI() {
        return "http://example.org/semop/function/echo";
    }

    @Override
    public Value evaluate(ValueFactory valueFactory, Value... args)
            throws ValueExprEvaluationException {

        if (args.length != 1) {
            throw new ValueExprEvaluationException(
                "Echo function expects exactly one argument"
            );
        }

        return valueFactory.createLiteral(args[0].stringValue());
    }
}
