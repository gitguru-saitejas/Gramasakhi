'use client';

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUiStore } from '@/stores/ui-store';
import { useLanguageStore } from '@/stores/language-store';
import { useAuth } from '../../../context/AuthContext';
import { CITIZEN_LANGUAGES } from '@/lib/i18n/translations';
import { useDialogA11y } from '@/lib/hooks/use-dialog-a11y';
import { X, User, Save, LogOut } from 'lucide-react';

export function UserProfileModal() {
  const { activeModal, closeModal, userProfile, updateUserProfile } = useUiStore();
  const { currentLanguage, setLanguage } = useLanguageStore();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const isOpen = activeModal === 'user_profile';
  const dialogRef = useDialogA11y(isOpen, closeModal);

  const [form, setForm] = useState({
    name: userProfile.name || '',
    state: userProfile.state || 'Karnataka',
    district: userProfile.district || 'Mandya',
    occupation: userProfile.occupation || 'Small Farmer (< 2 Hectares)',
    rationCardType: userProfile.rationCardType || 'BPL (Priority Household)',
  });

  if (!isOpen) return null;

  const handleSave = (e) => {
    e.preventDefault();
    updateUserProfile(form);
    closeModal();
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-profile-title"
        tabIndex={-1}
        className="bg-surface-container-lowest w-full max-w-lg max-h-[90vh] rounded-[32px] shadow-2xl flex flex-col overflow-hidden border border-surface-variant animate-fadeIn outline-none"
      >
        
        {/* Header */}
        <div className="p-6 border-b border-surface-variant flex items-center justify-between bg-surface-container-low">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold">
              <User className="w-5 h-5 text-tertiary-fixed-dim" />
            </div>
            <div>
              <h2 id="user-profile-title" className="text-lg text-primary font-bold">Citizen Profile & Settings</h2>
              <p className="text-xs text-on-surface-variant">Personalize scheme matching for your household</p>
            </div>
          </div>
          <button
            onClick={closeModal}
            type="button"
            aria-label="Close dialog"
            className="w-9 h-9 rounded-full hover:bg-surface-variant flex items-center justify-center text-on-surface-variant focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSave} className="p-6 overflow-y-auto custom-scrollbar space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-primary mb-1">Full Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full p-2.5 rounded-xl border border-surface-variant bg-surface-container-low focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-primary mb-1">State</label>
              <select
                value={form.state}
                onChange={(e) => setForm({ ...form, state: e.target.value })}
                className="w-full p-2.5 rounded-xl border border-surface-variant bg-surface-container-low"
              >
                <option value="Karnataka">Karnataka</option>
                <option value="Maharashtra">Maharashtra</option>
                <option value="Tamil Nadu">Tamil Nadu</option>
                <option value="Andhra Pradesh">Andhra Pradesh</option>
                <option value="Uttar Pradesh">Uttar Pradesh</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-primary mb-1">District</label>
              <input
                type="text"
                value={form.district}
                onChange={(e) => setForm({ ...form, district: e.target.value })}
                className="w-full p-2.5 rounded-xl border border-surface-variant bg-surface-container-low"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-primary mb-1">Primary Occupation</label>
              <select
                value={form.occupation}
                onChange={(e) => setForm({ ...form, occupation: e.target.value })}
                className="w-full p-2.5 rounded-xl border border-surface-variant bg-surface-container-low"
              >
                <option value="Small Farmer (< 2 Hectares)">Small Farmer (&lt; 2 Ha)</option>
                <option value="Agricultural Laborer">Agricultural Laborer</option>
                <option value="Artisan / Weaver">Artisan / Weaver</option>
                <option value="Self-Employed / Shopkeeper">Self-Employed</option>
                <option value="Student">Student</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-primary mb-1">Ration Card Type</label>
              <select
                value={form.rationCardType}
                onChange={(e) => setForm({ ...form, rationCardType: e.target.value })}
                className="w-full p-2.5 rounded-xl border border-surface-variant bg-surface-container-low"
              >
                <option value="BPL (Priority Household)">BPL (Priority / PHH)</option>
                <option value="AAY (Antyodaya)">AAY (Antyodaya)</option>
                <option value="APL (Non-Priority)">APL (Non-Priority)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-primary mb-1">Default Language</label>
            <select
              value={currentLanguage}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full p-2.5 rounded-xl border border-surface-variant bg-surface-container-low"
            >
              {CITIZEN_LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name} ({lang.englishName})
                </option>
              ))}
            </select>
          </div>

          <div className="pt-4 border-t border-surface-variant flex flex-col sm:flex-row sm:justify-between gap-2">
            <button
              type="button"
              onClick={() => {
                closeModal();
                logout();
                navigate('/');
              }}
              className="px-4 py-2 text-error font-bold rounded-full text-xs flex items-center justify-center gap-1.5 hover:bg-error-container/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-error/30"
            >
              <LogOut className="w-3.5 h-3.5" />
              Sign out
            </button>
            <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={closeModal}
              className="px-4 py-2 border border-outline-variant text-on-surface rounded-full text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 bg-primary text-on-primary rounded-full text-xs font-bold hover:bg-surface-tint flex items-center gap-1.5 shadow-sm"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Save Profile</span>
            </button>
            </div>
          </div>
        </form>

      </div>
    </div>
  );
}
