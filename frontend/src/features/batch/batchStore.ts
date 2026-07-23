import { create } from "zustand";
import { apiClient } from "@/lib/apiClient";

export type BatchItem = {
  id: string;
  ref_id: string;
  status: string;
  result: Record<string, unknown>;
  error: string;
};

export type BatchJob = {
  id: string;
  job_type: string;
  status: string;
  total: number;
  done: number;
  success: number;
  failed: number;
  items?: BatchItem[];
};

type BatchState = {
  open: boolean;
  minimized: boolean;
  batch: BatchJob | null;
  polling: boolean;
  openBatch: (batchId: string) => Promise<void>;
  setMinimized: (v: boolean) => void;
  close: () => void;
};

async function fetchBatch(id: string) {
  const { data } = await apiClient.get<BatchJob>(`/logistics/batches/${id}/`);
  return data;
}

export const useBatchConsole = create<BatchState>((set, get) => ({
  open: false,
  minimized: false,
  batch: null,
  polling: false,
  setMinimized: (v) => set({ minimized: v }),
  close: () => set({ open: false, batch: null, polling: false, minimized: false }),
  openBatch: async (batchId: string) => {
    set({ open: true, minimized: false, polling: true });
    let data = await fetchBatch(batchId);
    set({ batch: data });
    for (let i = 0; i < 90; i++) {
      if (!get().open) break;
      await new Promise((r) => setTimeout(r, 2000));
      data = await fetchBatch(batchId);
      set({ batch: data });
      if (data.status === "COMPLETED" || data.status === "CANCELLED") break;
    }
    set({ polling: false });
  },
}));
