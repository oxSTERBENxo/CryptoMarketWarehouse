import { getWarehouseHealth } from "../api/health";
import { useApiData } from "../hooks/useApiData";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { HealthStatusBadge } from "../components/HealthStatusBadge";
import { HealthCheckCard } from "../components/HealthCheckCard";
import { formatDate, formatDateTime, formatNumber } from "../utils/format";
import type { EtlRunInfo } from "../api/types";
import "../components/OverviewCards.css";
import "../components/Table.css";
import "./WarehouseHealth.css";

function runSummary(run: EtlRunInfo | null): string {
  if (!run) return "None recorded yet";
  return `${run.pipeline_name} (run #${run.run_id}) — ${formatDateTime(run.finished_at ?? run.started_at)}`;
}

export function WarehouseHealth() {
  const health = useApiData(getWarehouseHealth);
  const data = health.data;

  return (
    <main className="warehouse-health">
      <div className="warehouse-health__header">
        <div>
          <h1 className="warehouse-health__title">Warehouse Health</h1>
          <p className="warehouse-health__subtitle">
            Deterministic checks over the warehouse's own state — no AI, nothing estimated.
          </p>
        </div>
        <button
          type="button"
          className="warehouse-health__refresh"
          onClick={health.retry}
          disabled={health.loading}
        >
          {health.loading && <span className="status-spinner" aria-hidden="true" />}
          Refresh
        </button>
      </div>

      {health.loading && <LoadingState label="Checking warehouse health..." />}
      {!health.loading && health.error && <ErrorState message={health.error} onRetry={health.retry} />}

      {!health.loading && !health.error && data && (
        <>
          <div className="warehouse-health__overall" aria-live="polite">
            <span>Overall status:</span>
            <HealthStatusBadge status={data.overall_status} />
            <span className="warehouse-health__generated-at">as of {formatDateTime(data.generated_at)}</span>
            <span className="warehouse-health__environment">{data.environment}</span>
          </div>

          <section aria-labelledby="warehouse-health-checks-heading">
            <h2 id="warehouse-health-checks-heading">Checks</h2>
            <div className="health-checks-grid">
              <HealthCheckCard title="Database" check={data.database} />
              <HealthCheckCard title="Data Quality (last 7 days)" check={data.data_quality} />
              <HealthCheckCard title="Duplicate Check" check={data.duplicate_check} />
              <HealthCheckCard title="Missing-Date Coverage" check={data.missing_date_coverage} />
              <HealthCheckCard title="Stale Coins" check={data.stale_coin_check} />
              <HealthCheckCard title="Scheduler" check={data.scheduler} />
            </div>
          </section>

          <section aria-labelledby="warehouse-health-stats-heading">
            <h2 id="warehouse-health-stats-heading">Warehouse Statistics</h2>
            <dl className="overview-grid">
              <div className="overview-card">
                <dt>Last Daily Snapshot</dt>
                <dd>{formatDate(data.last_daily_snapshot_date)}</dd>
              </div>
              <div className="overview-card">
                <dt>Last Hourly Snapshot</dt>
                <dd>{formatDateTime(data.last_hourly_snapshot_at)}</dd>
              </div>
              <div className="overview-card">
                <dt>Daily Fact Rows</dt>
                <dd>{formatNumber(data.daily_fact_row_count)}</dd>
              </div>
              <div className="overview-card">
                <dt>Hourly Fact Rows</dt>
                <dd>{formatNumber(data.hourly_fact_row_count)}</dd>
              </div>
              <div className="overview-card">
                <dt>Current Coins</dt>
                <dd>{formatNumber(data.current_coin_count)}</dd>
              </div>
              <div className="overview-card">
                <dt>Historical Coin Versions</dt>
                <dd>{formatNumber(data.historical_coin_version_count)}</dd>
              </div>
            </dl>
          </section>

          <section aria-labelledby="warehouse-health-runs-heading">
            <h2 id="warehouse-health-runs-heading">Pipeline Runs</h2>
            <dl className="warehouse-health__runs">
              <div className="warehouse-health__run-row">
                <dt>Latest successful run</dt>
                <dd>{runSummary(data.latest_successful_run)}</dd>
              </div>
              <div className="warehouse-health__run-row">
                <dt>Latest failed run</dt>
                <dd>
                  {runSummary(data.latest_failed_run)}
                  {data.latest_failed_run?.error_message && (
                    <span className="warehouse-health__run-error"> — {data.latest_failed_run.error_message}</span>
                  )}
                </dd>
              </div>
            </dl>
          </section>

          {data.missing_dates.length > 0 && (
            <section aria-labelledby="warehouse-health-missing-dates-heading">
              <h2 id="warehouse-health-missing-dates-heading">Missing Dates ({data.missing_dates.length})</h2>
              <ul className="warehouse-health__missing-dates">
                {data.missing_dates.map((d) => (
                  <li key={d}>{formatDate(d)}</li>
                ))}
              </ul>
            </section>
          )}

          {data.stale_coins.length > 0 && (
            <section aria-labelledby="warehouse-health-stale-coins-heading">
              <h2 id="warehouse-health-stale-coins-heading">Stale Coins ({data.stale_coins.length})</h2>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Symbol</th>
                      <th scope="col">Coin ID</th>
                      <th scope="col">Last Seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.stale_coins.map((coin) => (
                      <tr key={coin.coin_id}>
                        <td className="symbol-cell">{coin.symbol}</td>
                        <td>{coin.coin_id}</td>
                        <td>{formatDate(coin.last_seen_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}
