import { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { getGraphSnapshots, getGraphValues } from "../services/graph";
import { useLotteryStore } from "../store/useLotteryStore";
import type { GraphSnapshotInfo } from "../types/graph";

const ForceGraph2D = lazy(() => import("react-force-graph-2d"));

const NO_LOTTERY_MESSAGE = "Select a lottery to see the network graph.";
const NO_DATA_MESSAGE = "No network snapshot for this lottery yet.";
const NO_LINKS_MESSAGE = "No co-occurrence links in this snapshot.";
const GRAPH_HEIGHT = 480;
const GRAPH_ARIA_LABEL = "Network graph of lottery numbers";
const COMMUNITY_COLORS = [
  "#3b82f6",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
];

interface GraphNode {
  id: string;
  name: string;
  val: number;
  color?: string;
}

interface GraphLink {
  source: string;
  target: string;
  value: number;
}

interface NetworkGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
}

function snapshotClass(selected: boolean): string {
  return `flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border px-3 py-2 text-left text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
    selected
      ? "border-blue-600 bg-blue-50 text-gray-900"
      : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
  }`;
}

/** Canvas wrapper around the lazy-loaded force graph; exposes a testable container. */
function NetworkGraph({ nodes, links }: NetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    setWidth(el.clientWidth || 640);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(w);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={containerRef}
      data-testid="network-graph"
      role="img"
      aria-label={GRAPH_ARIA_LABEL}
      className="overflow-hidden rounded-md border border-gray-200"
    >
      <Suspense fallback={<Skeleton variant="card" />}>
        <ForceGraph2D
          graphData={{ nodes, links }}
          nodeLabel="name"
          nodeVal="val"
          linkWidth={(link) => Math.max(0.5, (link.value ?? 1) / 5)}
          width={width}
          height={GRAPH_HEIGHT}
        />
      </Suspense>
    </div>
  );
}

/** Redes page: snapshot list + select → force-directed co-occurrence network graph. */
export default function Networks() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const {
    data: snapshotList,
    isLoading: loadingList,
    error: listError,
    execute: fetchSnapshots,
  } = useApi(getGraphSnapshots);
  const {
    data: values,
    isLoading: loadingValues,
    error: valuesError,
    execute: fetchValues,
  } = useApi(getGraphValues);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    if (!selectedLotteryCode) return;
    setSelectedId(null);
    void fetchSnapshots(selectedLotteryCode, "network");
  }, [selectedLotteryCode, fetchSnapshots]);

  useEffect(() => {
    if (selectedId !== null || !snapshotList) return;
    const latest = snapshotList.snapshots[0];
    if (latest) setSelectedId(latest.snapshot_id);
  }, [snapshotList, selectedId]);

  useEffect(() => {
    if (!selectedLotteryCode || selectedId === null) return;
    void fetchValues(selectedLotteryCode, selectedId);
  }, [selectedLotteryCode, selectedId, fetchValues]);

  const { nodes, links } = useMemo(() => {
    const rows = values?.rows ?? [];
    const degree = new Map<string, number>();
    const community = new Map<string, number>();
    const links: GraphLink[] = [];
    const seen = new Set<string>();
    for (const row of rows) {
      if (row.metric_type === "centrality_degree") degree.set(row.subject, row.value);
      else if (row.metric_type === "community_id") community.set(row.subject, row.value);
      else if (row.metric_type === "cooccurrence") {
        const [i, j] = row.subject.split("-");
        if (!i || !j) continue;
        links.push({ source: i, target: j, value: row.value });
        seen.add(i);
        seen.add(j);
      }
    }
    const nodes: GraphNode[] = [];
    for (const id of seen) nodes.push({ id, name: id, val: degree.get(id) ?? 1 });
    for (const [id, val] of degree) if (!seen.has(id)) nodes.push({ id, name: id, val });
    for (const node of nodes) {
      const cid = community.get(node.id);
      if (cid !== undefined) node.color = COMMUNITY_COLORS[cid % COMMUNITY_COLORS.length];
    }
    return { nodes, links };
  }, [values]);

  const snapshots = snapshotList?.snapshots ?? [];
  const selected = snapshots.find((item) => item.snapshot_id === selectedId) ?? null;

  const renderVisualization = (code: string, item: GraphSnapshotInfo) => {
    if (valuesError)
      return (
        <ErrorState
          message={valuesError}
          onRetry={() => void fetchValues(code, item.snapshot_id)}
        />
      );
    if (loadingValues) return <Skeleton variant="card" />;
    if (links.length === 0) return <EmptyState message={NO_LINKS_MESSAGE} />;
    return (
      <div className="space-y-4">
        <NetworkGraph nodes={nodes} links={links} />
        <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
          <span>
            Draws <span className="font-medium text-gray-900">{item.draw_count}</span>
          </span>
          <span>
            Nodes <span className="font-medium text-gray-900">{nodes.length}</span>
          </span>
          <span>
            Links <span className="font-medium text-gray-900">{links.length}</span>
          </span>
        </p>
      </div>
    );
  };

  const renderContent = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (listError)
      return (
        <ErrorState
          message={listError}
          onRetry={() => void fetchSnapshots(selectedLotteryCode, "network")}
        />
      );
    if (loadingList) return <Skeleton variant="card" />;
    if (snapshots.length === 0) return <EmptyState message={NO_DATA_MESSAGE} />;
    return (
      <div className="space-y-5">
        <ul className="flex flex-col gap-2 sm:max-w-md" aria-label="Network snapshots">
          {snapshots.map((item) => (
            <li key={item.snapshot_id}>
              <button
                type="button"
                aria-pressed={selectedId === item.snapshot_id}
                onClick={() => setSelectedId(item.snapshot_id)}
                className={snapshotClass(selectedId === item.snapshot_id)}
              >
                <span className="font-medium">#{item.snapshot_id}</span>
                <span>
                  v{item.version} · {item.draw_count} draws · {item.status} ·{" "}
                  {new Date(item.created_at).toLocaleDateString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {selected ? renderVisualization(selectedLotteryCode, selected) : null}
      </div>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Networks</h2>
        <p className="text-sm text-gray-500">
          Co-occurrence network between lottery numbers for the selected lottery.
        </p>
      </div>
      <section
        aria-label="Network graph"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderContent()}
      </section>
    </div>
  );
}
