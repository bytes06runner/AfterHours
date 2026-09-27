"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, createElement, useContext, useEffect, useState } from "react";

import { api, STREAM_EVENTS, streamUrl, type StreamEvent } from "./api";

const MINUTE = 60_000;

export const keys = {
  config: ["config"] as const,
  status: ["status"] as const,
  vault: ["vault"] as const,
  prices: ["prices"] as const,
  risk: ["risk"] as const,
  almanac: (days: number) => ["almanac", days] as const,
  reasons: (stock?: string) => ["reasons", stock ?? "all"] as const,
  reason: (id: string) => ["reason", id] as const,
  reportCard: ["report-card"] as const,
  scenarios: ["scenarios"] as const,
  replay: (id: string) => ["replay", id] as const,
};

export const useConfig = () =>
  useQuery({ queryKey: keys.config, queryFn: api.config, staleTime: 10 * MINUTE });
export const useStatus = () =>
  useQuery({ queryKey: keys.status, queryFn: api.status, refetchInterval: MINUTE, retry: 1 });
export const useVault = () => useQuery({ queryKey: keys.vault, queryFn: api.vault, retry: 1 });
export const usePrices = () =>
  useQuery({ queryKey: keys.prices, queryFn: api.prices, refetchInterval: MINUTE, retry: 1 });
export const useRisk = () => useQuery({ queryKey: keys.risk, queryFn: api.risk, retry: 1 });
export const useAlmanac = (days: number) =>
  useQuery({ queryKey: keys.almanac(days), queryFn: () => api.almanac(days), retry: 1 });
export const useLiveBoard = () =>
  // More retries: right after the API starts, the first board can take a minute to read.
  useQuery({ queryKey: ["live-board"], queryFn: api.liveBoard, refetchInterval: MINUTE, retry: 6 });
export const useLiveExamples = () =>
  useQuery({ queryKey: ["live-examples"], queryFn: api.liveExamples, staleTime: 10 * MINUTE });
export const useLivePositions = (address: string | null) =>
  useQuery({
    queryKey: ["live-positions", address ?? ""],
    queryFn: () => api.livePositions(address!),
    enabled: Boolean(address),
    retry: 0,
  });
export const useReportCard = () =>
  useQuery({ queryKey: keys.reportCard, queryFn: api.reportCard, staleTime: 60 * MINUTE });
export const useScenarios = () =>
  useQuery({ queryKey: keys.scenarios, queryFn: api.scenarios, staleTime: 60 * MINUTE });
export const useReplay = (id: string | null) =>
  useQuery({
    queryKey: keys.replay(id ?? ""),
    queryFn: () => api.replay(id!),
    enabled: Boolean(id),
    staleTime: 60 * MINUTE,
  });

/** Which queries each server event makes stale. */
const INVALIDATES: Record<StreamEvent, readonly (readonly string[])[]> = {
  status: [keys.status, keys.prices],
  plan_changed: [keys.risk, keys.vault],
  tx_sent: [],
  tx_confirmed: [keys.vault],
  reason_logged: [["reasons"]],
  vault_updated: [keys.vault],
};

export interface LiveEvent {
  type: StreamEvent;
  data: unknown;
  at: number;
}

/** Subscribe to /v1/stream; refresh affected queries and expose the latest event. */
export function useLiveStream(): { last: LiveEvent | null; connected: boolean } {
  const client = useQueryClient();
  const [last, setLast] = useState<LiveEvent | null>(null);
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let source: EventSource;
    try {
      source = new EventSource(streamUrl());
    } catch {
      return;
    }
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    const handlers = STREAM_EVENTS.map((type) => {
      const handler = (e: MessageEvent<string>) => {
        let data: unknown = null;
        try {
          data = JSON.parse(e.data);
        } catch {
          /* keep null */
        }
        for (const key of INVALIDATES[type]) void client.invalidateQueries({ queryKey: key });
        setLast({ type, data, at: Date.now() });
      };
      source.addEventListener(type, handler as EventListener);
      return [type, handler] as const;
    });
    return () => {
      for (const [type, handler] of handlers)
        source.removeEventListener(type, handler as EventListener);
      source.close();
    };
  }, [client]);
  return { last, connected };
}

const LiveContext = createContext<{ last: LiveEvent | null; connected: boolean }>({
  last: null,
  connected: false,
});

/** The app's one event-stream subscription; children read it with useLiveEvent. */
export function LiveStreamProvider({ children }: { children: React.ReactNode }) {
  const value = useLiveStream();
  return createElement(LiveContext.Provider, { value }, children);
}

export const useLiveEvent = () => useContext(LiveContext);
