import { useMemo } from "react";
import { api } from "../api/client";
import { useAsync } from "./useAsync";

async function loadDepartments() {
  return (await api.get("/departments")).data;
}

/** Departments plus an id -> department lookup. */
export function useDepartments() {
  const state = useAsync(loadDepartments);
  const byId = useMemo(
    () => Object.fromEntries((state.data ?? []).map((d) => [d.id, d])),
    [state.data],
  );
  return { ...state, list: state.data ?? [], byId };
}
