import { ASPECTS } from "../api/evaluation";

export const SKIP_REASONS = [
  ["not_english", "Not in English"],
  ["not_about_teaching", "Not about teaching"],
  ["unclear", "Can't tell"],
];

export function emptyJudgement() {
  return { sentiment: null, aspects: {}, sarcastic: false };
}

/** {key: polarity} -> [{key, polarity}] in questionnaire order. */
export function aspectList(map) {
  return ASPECTS.filter(([key]) => map[key]).map(([key]) => ({ key, polarity: map[key] }));
}
