import { create } from "zustand";

export const useUiStore = create((set) => ({
  isMobileSidebarOpen: false,
  isLanguageDropdownOpen: false,
  activeModal: null,
  selectedSchemeForModal: null,

  userProfile: {
    name: "Citizen",
    state: "",
    district: "",
  },

  openMobileSidebar: () => set({ isMobileSidebarOpen: true }),
  closeMobileSidebar: () => set({ isMobileSidebarOpen: false }),
  toggleMobileSidebar: () =>
    set((state) => ({ isMobileSidebarOpen: !state.isMobileSidebarOpen })),

  setLanguageDropdownOpen: (isOpen) => set({ isLanguageDropdownOpen: isOpen }),
  toggleLanguageDropdown: () =>
    set((state) => ({ isLanguageDropdownOpen: !state.isLanguageDropdownOpen })),

  openModal: (modalName, schemeData = null) => {
    set({ activeModal: modalName, selectedSchemeForModal: schemeData });
  },
  closeModal: () => set({ activeModal: null, selectedSchemeForModal: null }),

  updateUserProfile: (newProfile) => {
    set((state) => ({
      userProfile: { ...state.userProfile, ...newProfile },
    }));
    if (typeof window !== "undefined") {
      localStorage.setItem("gramsakhi_profile", JSON.stringify(newProfile));
    }
  },

  initProfileFromStorage: () => {
    const phone =
      typeof window !== "undefined"
        ? localStorage.getItem("citizenPhone") || localStorage.getItem("phoneNumber")
        : null;
    if (phone) {
      set((state) => ({
        userProfile: { ...state.userProfile, name: phone.slice(-4) ? `Citizen ···${phone.slice(-4)}` : "Citizen" },
      }));
    }
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("gramsakhi_profile");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          set((state) => ({ userProfile: { ...state.userProfile, ...parsed } }));
        } catch {
          // ignore
        }
      }
    }
  },
}));
