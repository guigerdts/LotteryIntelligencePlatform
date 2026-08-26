import { useCallback, useState, type FormEvent } from "react";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import Skeleton from "./Skeleton";
import {
  assist,
  explainAssistant,
  interpretAssistant,
  reportAssistant,
  summarizeAssistant,
} from "../services/assistant";
import type { AssistantResponse } from "../types/assistant";

interface AssistantPanelProps {
  lotteryCode: string | null;
}

type PanelAction = () => Promise<AssistantResponse>;

const NO_LOTTERY_MESSAGE = "Selecciona una lotería para consultar al asistente IA.";
const FIELD_CLASS =
  "w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";
const BUTTON_CLASS =
  "rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

/**
 * AI assistant panel (R14, D4): free-text question bound to the lottery
 * selector plus four explicit actions (explain/interpret/report/summarize)
 * guaranteeing all five /assistant endpoints (NFR-2). Own loading/error/empty
 * state (R20); empty-data text renders as content, never as an error.
 */
export default function AssistantPanel({ lotteryCode }: AssistantPanelProps) {
  const [question, setQuestion] = useState("");
  const [experimentId, setExperimentId] = useState("");
  const [result, setResult] = useState<AssistantResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [retry, setRetry] = useState<PanelAction | null>(null);

  const run = useCallback((action: PanelAction) => {
    setResult(null);
    setError(null);
    setIsLoading(true);
    setRetry(() => action);
    action()
      .then((response) => {
        setResult(response);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Unknown error");
        setIsLoading(false);
      });
  }, []);

  const handleAssist = (event: FormEvent) => {
    event.preventDefault();
    if (!lotteryCode || question.trim() === "") return;
    run(() => assist(question.trim(), lotteryCode));
  };

  const experimentIdNumber = Number(experimentId);
  const hasExperimentId = Number.isInteger(experimentIdNumber) && experimentIdNumber > 0;

  if (!lotteryCode) {
    return (
      <section
        aria-labelledby="ia-assistant-title"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        <h3 id="ia-assistant-title" className="mb-3 text-sm font-semibold text-gray-900">
          Asistente IA
        </h3>
        <EmptyState message={NO_LOTTERY_MESSAGE} />
      </section>
    );
  }

  const actions = [
     { label: "Explicar", onRun: () => run(() => explainAssistant(lotteryCode)) },
    {
      label: "Interpretar",
      onRun: () => run(() => interpretAssistant(lotteryCode)),
    },
     { label: "Informe", onRun: () => run(() => reportAssistant(lotteryCode)) },
  ];

  const renderResult = () => {
    if (isLoading) return <Skeleton variant="card" />;
    if (error) {
      return (
        <ErrorState
          message={error}
          onRetry={() => {
            if (retry) run(retry);
          }}
        />
      );
    }
    if (result) {
      return (
        <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
          <p className="whitespace-pre-wrap text-sm text-gray-900">{result.text}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <section
      aria-labelledby="ia-assistant-title"
      className="rounded-md border border-gray-200 bg-white p-4"
    >
        <h3 id="ia-assistant-title" className="mb-3 text-sm font-semibold text-gray-900">
          Asistente IA
        </h3>
        <div className="space-y-4">
        <form onSubmit={handleAssist} className="space-y-2">
          <label
            htmlFor="assistant-question"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            Haz una pregunta sobre esta lotería
          </label>
          <textarea
            id="assistant-question"
            rows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="¿Por qué cambió la frecuencia del número 5?"
            className={FIELD_CLASS}
          />
          <button type="submit" disabled={question.trim() === ""} className={BUTTON_CLASS}>
            Preguntar
          </button>
        </form>
        <div className="flex flex-wrap items-end gap-3">
          {actions.map(({ label, onRun }) => (
            <button key={label} type="button" onClick={onRun} className={BUTTON_CLASS}>
              {label}
            </button>
          ))}
          <div>
            <label
              htmlFor="assistant-experiment-id"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              ID del experimento
            </label>
            <div className="flex gap-2">
              <input
                id="assistant-experiment-id"
                type="number"
                min={1}
                value={experimentId}
                onChange={(event) => setExperimentId(event.target.value)}
                className={`${FIELD_CLASS} w-32`}
              />
              <button
                type="button"
                onClick={() => {
                  if (hasExperimentId) {
                    run(() => summarizeAssistant({ experiment_id: experimentIdNumber }));
                  }
                }}
                disabled={!hasExperimentId}
                className={BUTTON_CLASS}
              >
                 Resumir
              </button>
            </div>
          </div>
        </div>
        <div aria-live="polite">{renderResult()}</div>
      </div>
    </section>
  );
}
