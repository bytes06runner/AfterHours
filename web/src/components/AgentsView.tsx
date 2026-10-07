"use client";

/**
 * Agents: how to give an AI agent Afterhours' read-only weekend risk, in under a minute.
 * The install command, tools and REST paths come from /v1/config/public and the API base URL;
 * the session at the end is a captured run of real tool calls (/v1/agents/example-session).
 */
import { useState } from "react";

import { apiBase, type AgentSession } from "@/lib/api";
import { useAgentSession, useConfig } from "@/lib/queries";

import { ZonedTime } from "./ZonedTime";

const TOOLS = [
  {
    name: "market_status()",
    does: "Is the US exchange open, when it next opens and closes, whether Stock Token feeds are posting, and how many Stock Tokens sit in each price regime.",
    path: "/v1/agent/market-status",
  },
  {
    name: "get_weekend_risk(ticker)",
    does: "One Stock Token: price regime and price quality, the next closed period, its bad-case drop with the measured held-out miss rate for that kind of night, which USDG Morpho markets' cushions that passes, and a plain paragraph.",
    path: "/v1/agent/weekend-risk/NVDA",
  },
  {
    name: "check_position(address)",
    does: "Every Morpho loan a wallet holds against a Stock Token: borrowed, LTV, liquidation price, and whether tonight's bad case reaches it.",
    path: "/v1/agent/positions/{address}",
  },
  {
    name: "explain_move(reason_id)",
    does: "Why the vault moved: the reason card the bot wrote and whether its hash matches the event onchain.",
    path: "/v1/agent/moves/{reason_id}",
  },
];

function api(): string | null {
  try {
    return apiBase().replace(/\/$/, "");
  } catch {
    return null;
  }
}

function CopyBlock({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative mt-3">
      <pre className="overflow-x-auto rounded-[12px] border-[1.25px] border-rule bg-surface p-4 pr-20 text-[14px] leading-relaxed">
        <code>{text}</code>
      </pre>
      <button
        type="button"
        className="btn btn-quiet absolute top-2 right-2 !min-h-[36px] !text-[14px]"
        onClick={() => {
          void navigator.clipboard?.writeText(text).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          });
        }}
        aria-label={`Copy ${label}`}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

type Step = Extract<AgentSession["session"][number], { tool: string }>;

function Session({ s }: { s: AgentSession }) {
  const steps = s.session.filter((x): x is Step => "tool" in x);
  return (
    <div className="mt-4 flex flex-col gap-5" data-testid="agent-session">
      {steps.map((st, i) => (
        <div key={i} className="flex flex-col gap-2">
          <p className="text-[18px]">
            <span className="font-semibold">You ask:</span> {st.question}
          </p>
          <p className="text-[14px]">
            The agent calls{" "}
            <code className="rounded-[6px] bg-surface px-1.5 py-0.5 break-all">
              {st.tool}(
              {Object.values(st.arguments)
                .map((v) => JSON.stringify(v))
                .join(", ")}
              )
            </code>
          </p>
          <blockquote className="max-w-[72ch] rounded-[12px] border-[1.25px] border-rule bg-surface p-4 text-[16px]">
            {typeof st.result.summary === "string"
              ? st.result.summary
              : "The tool returned no summary."}
          </blockquote>
        </div>
      ))}
      <p className="text-[14px] break-words">
        Captured <ZonedTime iso={s.captured_at} /> from {s.api}, with the server started as{" "}
        <code className="break-all">{s.server_started_with}</code>. {s.note}
      </p>
    </div>
  );
}

export function AgentsView() {
  const { data: cfg } = useConfig();
  const session = useAgentSession();
  const base = api();
  const a = cfg?.agents;
  const desktop =
    a && base
      ? JSON.stringify(
          {
            mcpServers: {
              afterhours: {
                command: "uvx",
                args: ["--from", a.mcp_source, a.mcp_command],
                env: { [a.api_url_env]: base },
              },
            },
          },
          null,
          2,
        )
      : null;
  const shell =
    a && base ? `${a.api_url_env}=${base} uvx --from "${a.mcp_source}" ${a.mcp_command}` : null;
  return (
    <div className="mx-auto max-w-[1440px] px-4 pb-24 [overflow-wrap:anywhere] sm:px-8">
      <h1 className="mt-8 text-[48px] lg:text-[64px]">Agents</h1>
      <p className="mt-4 max-w-[70ch] text-[18px]">
        Robinhood has announced AI trading agents whose Loops can run a strategy around the clock,
        overnight included. An agent that acts while you sleep needs to know when a Stock
        Token&apos;s price stops meaning much. Afterhours gives any MCP client four tools for that.
      </p>
      <p className="badge mt-4 !border-safe">
        Read-only: no tool can sign, send or trade, and the server holds no key.
      </p>

      <section className="mt-12" aria-labelledby="connect">
        <h2 id="connect" className="text-[36px]">
          Connect Claude Desktop in under a minute
        </h2>
        <ol className="mt-4 flex max-w-[72ch] list-decimal flex-col gap-4 pl-6 text-[18px] [&>li]:min-w-0">
          <li>Install uv, the Python tool runner from Astral, if you do not have it.</li>
          <li>
            In Claude Desktop open Settings, Developer, Edit Config, and add this to{" "}
            <code>claude_desktop_config.json</code>:
            {desktop ? (
              <CopyBlock text={desktop} label="Claude Desktop config" />
            ) : (
              <p className="mt-2">Reading the API address.</p>
            )}
          </li>
          <li>
            Restart Claude Desktop and ask: &ldquo;Is NVDA safe to lend against this weekend?&rdquo;
          </li>
        </ol>
        <p className="mt-6 max-w-[72ch] text-[16px]">
          Any other MCP client starts the same server over stdio:
        </p>
        {shell && <CopyBlock text={shell} label="command" />}
      </section>

      <section className="mt-12" aria-labelledby="tools">
        <h2 id="tools" className="text-[36px]">
          The tools, and the same data over REST
        </h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead>
              <tr className="text-[14px]">
                {["Tool", "Answers", "REST"].map((h) => (
                  <th key={h} className="border-b-[1.25px] border-rule py-2 pr-4 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {TOOLS.map((t) => (
                <tr key={t.name} className="align-top">
                  <td className="border-b-[1.25px] border-rule py-3 pr-4 font-semibold">
                    <code>{t.name}</code>
                  </td>
                  <td className="max-w-[56ch] border-b-[1.25px] border-rule py-3 pr-4 text-[16px]">
                    {t.does}
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4 text-[14px]">
                    <code>GET {t.path}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {base && (
          <p className="mt-4 max-w-[72ch] text-[16px]">
            OpenAPI schema at{" "}
            <a href={`${base}/openapi.json`} className="break-all underline">
              {base}/openapi.json
            </a>
            {a ? `; up to ${a.rate_limit_per_minute} requests a minute per client` : ""}. The hosted
            API sleeps when idle, so a first call can take about a minute.
          </p>
        )}
      </section>

      <section className="mt-12" aria-labelledby="session">
        <h2 id="session" className="text-[36px]">
          A captured session
        </h2>
        <p className="mt-2 max-w-[72ch] text-[18px]">
          A scripted MCP client, started exactly as the install steps above, called each tool
          against the hosted API. The questions are examples written for the script, not an AI
          conversation. Every tool call and every answer below is what the tools returned.
        </p>
        {session.data && <Session s={session.data} />}
        {!session.data && !session.isError && (
          <p aria-busy="true" className="mt-4 min-h-[200px]">
            Reading the captured session.
          </p>
        )}
        {session.isError && <p className="mt-4">The captured session is not available yet.</p>}
      </section>
      <p className="mt-12 max-w-[70ch] text-[14px]">
        Afterhours reads public data on Robinhood Chain mainnet. Not financial advice.
      </p>
    </div>
  );
}
