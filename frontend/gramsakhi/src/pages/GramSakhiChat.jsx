import React, { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { TtsPlaybackProvider } from "@/context/TtsPlaybackContext";
import { useChatStore } from "@/stores/chat-store";
import "../gramasakhi-ui/globals.css";

export default function GramSakhiChat() {
  const { conversationId: routeConvId } = useParams();
  const navigate = useNavigate();
  const setNavigate = useChatStore((s) => s.setNavigate);
  const fetchConversations = useChatStore((s) => s.fetchConversations);
  const syncRoute = useChatStore((s) => s.syncRoute);

  useEffect(() => {
    setNavigate(navigate);
  }, [navigate, setNavigate]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  useEffect(() => {
    syncRoute(routeConvId || null);
  }, [routeConvId, syncRoute]);

  return (
    <div className="gramsakhi-ui-root h-screen w-screen overflow-hidden" style={{ fontFamily: "var(--font-vietnam), sans-serif" }}>
      <TtsPlaybackProvider>
        <AppShell />
      </TtsPlaybackProvider>
    </div>
  );
}
