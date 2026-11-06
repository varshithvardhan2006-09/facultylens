import { errorMessage } from "../../api/client";
import { FormError } from "../../components/forms";

/** A failed load inside a tab: one sentence and Retry. */
export function Failed({ error, onRetry }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <FormError>{errorMessage(error, "Couldn't load it.")}</FormError>
      <button type="button" className="btn btn-ghost h-8 px-2" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
