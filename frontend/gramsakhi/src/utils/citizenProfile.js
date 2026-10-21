import { useUiStore } from "../gramasakhi-ui/stores/ui-store";

/** Sync citizen profile UI from auth API payloads (register/login). */
export function syncCitizenProfileFromAuth(data) {
  if (!data || typeof data !== "object") return;
  const name = (data.display_name || "").trim();
  const phone = data.phone_number;
  const patch = {};
  if (name) patch.name = name;
  if (phone) {
    patch.phone = phone;
    if (typeof window !== "undefined") {
      localStorage.setItem("citizenPhone", phone);
    }
  }
  if (Object.keys(patch).length === 0) return;
  useUiStore.getState().updateUserProfile(patch);
}
