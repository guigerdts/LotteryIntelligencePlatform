import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DataTable, { type DataColumn } from "./DataTable";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import Skeleton from "./Skeleton";

interface TestRow {
  id: number;
  name: string;
}

const columns: DataColumn<TestRow>[] = [
  { key: "id", label: "ID", sortable: true },
  {
    key: "name",
    label: "Name",
    sortable: true,
    render: (row) => <strong>{row.name}</strong>,
  },
];

const rows: TestRow[] = [
  { id: 2, name: "Bravo" },
  { id: 1, name: "Alpha" },
];

function renderTable(props: Partial<Parameters<typeof DataTable<TestRow>>[0]> = {}) {
  return render(
    <DataTable<TestRow>
      columns={columns}
      rows={rows}
      rowKey={(row) => String(row.id)}
      caption="Draws"
      {...props}
    />
  );
}

describe("DataTable", () => {
  it("renders the caption, column headers and cell values", () => {
    renderTable();

    expect(screen.getByText("Draws")).toHaveClass("sr-only");
    expect(screen.getByRole("columnheader", { name: "ID" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByText("Bravo")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });

  it("sorts rows when a sortable header is clicked", () => {
    renderTable();

    fireEvent.click(screen.getByRole("button", { name: /name/i }));

    const header = screen.getByRole("columnheader", { name: /name/i });
    expect(header).toHaveAttribute("aria-sort", "ascending");

    const firstDataRow = screen.getAllByRole("row")[1];
    expect(firstDataRow).toHaveTextContent("Alpha");
    expect(firstDataRow).not.toHaveTextContent("Bravo");
  });

  it("renders an empty message when there are no rows", () => {
    renderTable({ rows: [] });

    expect(screen.getByText(/no hay datos disponibles/i)).toBeInTheDocument();
  });

  it("renders skeleton rows while loading", () => {
    renderTable({ loading: true, loadingRows: 3 });

    expect(screen.getAllByRole("row")).toHaveLength(4);
    expect(screen.queryByText(/no hay datos disponibles/i)).not.toBeInTheDocument();
  });

  it("uses the render prop for custom cell content", () => {
    renderTable();

    const nameCell = screen.getByText("Bravo");
    expect(nameCell.tagName).toBe("STRONG");
  });

  it("toggles sort direction to descending on second click", () => {
    renderTable();

    fireEvent.click(screen.getByRole("button", { name: /name/i }));
    fireEvent.click(screen.getByRole("button", { name: /name/i }));

    const header = screen.getByRole("columnheader", { name: /name/i });
    expect(header).toHaveAttribute("aria-sort", "descending");

    const firstDataRow = screen.getAllByRole("row")[1];
    expect(firstDataRow).toHaveTextContent("Bravo");
  });

  it("resets to ascending when a different sortable column is clicked", () => {
    renderTable();

    fireEvent.click(screen.getByRole("button", { name: /name/i }));
    fireEvent.click(screen.getByRole("button", { name: /id/i }));

    const idHeader = screen.getByRole("columnheader", { name: /id/i });
    expect(idHeader).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getByText("↑")).toBeInTheDocument();
  });

  it("renders non-sortable columns as plain text without a button", () => {
    renderTable({
      columns: [
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
      ],
    });

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });

  it("renders a dash for null and undefined cell values", () => {
    renderTable({
      columns: [
        { key: "id", label: "ID" },
        { key: "name", label: "Name" },
      ],
      rows: [
        { id: 1, name: "Alpha" },
        { id: 2, name: null as unknown as string },
      ],
    });

    const dashCells = screen.getAllByText("—");
    expect(dashCells).toHaveLength(1);
  });

  it("stringifies object cell values", () => {
    // Object-valued cells need their own row shape; the shared TestRow helper
    // only covers the primitive columns above (tsc -b caught the mismatch).
    interface MetaRow {
      id: number;
      meta: Record<string, unknown>;
    }
    render(
      <DataTable<MetaRow>
        columns={[{ key: "meta", label: "Meta" }]}
        rows={[{ id: 1, meta: { nested: true } }]}
        rowKey={(row) => String(row.id)}
        caption="Meta"
      />
    );

    expect(screen.getByText('{"nested":true}')).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("renders the message in an alert role", () => {
    render(<ErrorState message="Server error — try again later" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Server error — try again later");
  });

  it("calls the retry callback when the retry button is clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Failed to load" onRetry={onRetry} />);

    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not render a retry button when no callback is provided", () => {
    render(<ErrorState message="Failed to load" />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("renders the message and an optional action", () => {
    render(
      <EmptyState message="No data available." action={<button type="button">Generate</button>} />
    );

    expect(screen.getByText("No data available.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate/i })).toBeInTheDocument();
  });
});

describe("Skeleton", () => {
  it("renders a pulse placeholder hidden from the accessibility tree", () => {
    const { container } = render(<Skeleton variant="card" className="w-1/2" />);

    const skeleton = container.querySelector("[aria-hidden=true]");
    expect(skeleton).not.toBeNull();
    expect(skeleton).toHaveClass("animate-pulse");
    expect(skeleton).toHaveClass("w-1/2");
  });
});
