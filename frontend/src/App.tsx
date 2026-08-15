/* eslint-disable react-refresh/only-export-components -- Router config module: defines small inline render components but exports the route config constants consumed by main and tests. */
import { lazy, Suspense } from "react";
import { createBrowserRouter, Outlet, type RouteObject } from "react-router-dom";
import EmptyState from "./components/EmptyState";
import Skeleton from "./components/Skeleton";
import DashboardLayout from "./layouts/DashboardLayout";

const Home = lazy(() => import("./pages/Home"));
const History = lazy(() => import("./pages/History"));
const Statistics = lazy(() => import("./pages/Statistics"));
const Generator = lazy(() => import("./pages/Generator"));

/** Lazy route element that renders the shared ComingSoon placeholder. */
function lazyPage(title: string) {
  return lazy(() =>
    import("./components/ComingSoon").then((module) => ({
      default: () => <module.default title={title} />,
    })),
  );
}

const Heatmaps = lazyPage("Heatmaps");
const Trends = lazyPage("Tendencias");
const MonteCarlo = lazyPage("Monte Carlo");
const Networks = lazyPage("Redes");
const AI = lazyPage("IA");
const Models = lazyPage("Modelos");
const Experiments = lazyPage("Experimentos");
const Backtesting = lazyPage("Backtesting");

/** Suspense fallback shown while a lazy page chunk loads. */
function PageFallback() {
  return (
    <div aria-busy="true" className="space-y-4 p-4 sm:p-6">
      <Skeleton variant="text" className="max-w-xs" />
      <Skeleton variant="card" />
      <Skeleton variant="card" />
    </div>
  );
}

/** 404 fallback rendered inside the layout for unknown routes. */
function NotFound() {
  return (
    <div className="space-y-6 p-4 sm:p-6">
      <h2 className="text-lg font-semibold text-gray-900">Page not found</h2>
      <EmptyState message="The requested route does not exist." />
    </div>
  );
}

/** All dashboard routes render inside DashboardLayout with lazy chunks and a shared Suspense fallback. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: (
      <DashboardLayout>
        <Suspense fallback={<PageFallback />}>
          <Outlet />
        </Suspense>
      </DashboardLayout>
    ),
    children: [
      { index: true, element: <Home /> },
      { path: "historial", element: <History /> },
      { path: "estadisticas", element: <Statistics /> },
      { path: "heatmaps", element: <Heatmaps /> },
      { path: "tendencias", element: <Trends /> },
      { path: "redes", element: <Networks /> },
      { path: "monte-carlo", element: <MonteCarlo /> },
      { path: "ia", element: <AI /> },
      { path: "modelos", element: <Models /> },
      { path: "experimentos", element: <Experiments /> },
      { path: "backtesting", element: <Backtesting /> },
      { path: "generador", element: <Generator /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
