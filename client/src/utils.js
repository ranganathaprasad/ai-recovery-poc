import { AVATAR_COLORS, C } from "./constants";

export const initials = (name = "") =>
  name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

export const avatarColor = (name = "") =>
  AVATAR_COLORS[(name.charCodeAt(0) || 0) % AVATAR_COLORS.length];

export const confidenceColor = (label) =>
  ({ High: C.accent, Medium: C.amber, Low: C.red }[label] || C.textMuted);

export const metricColor = (metric, val, cohort) => {
  if (!val || !cohort) return C.textMuted;
  if (metric === "pain") return val > cohort ? C.red : C.accent;
  return val >= cohort ? C.accent : C.amber;
};

export const fmt = (val, decimals = 1) =>
  typeof val === "number" ? val.toFixed(decimals) : "—";
