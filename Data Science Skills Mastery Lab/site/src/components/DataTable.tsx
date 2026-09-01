import type { Table } from "../types";

const STATUS = new Set(["PASS", "FAIL", "WARN", "OPEN", "ok", "hit", "miss"]);

export default function DataTable({ table }: { table: Table }) {
  return (
    <div>
      <h3>{table.title}</h3>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              {table.columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => {
                  const s = cell === null || cell === undefined ? "" : String(cell);
                  const isNum = typeof cell === "number";
                  return (
                    <td key={j} className={[isNum ? "num" : "", STATUS.has(s) ? `status-${s}` : ""].join(" ").trim()}>
                      {isNum ? cell.toLocaleString(undefined, { maximumFractionDigits: 4 }) : s}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.note && <div className="chart-note">{table.note}</div>}
    </div>
  );
}
