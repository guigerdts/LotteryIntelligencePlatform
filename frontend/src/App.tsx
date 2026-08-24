/* eslint-disable react-refresh/only-export-components -- Router config module: defines small inline render components but exports the route config constants consumed by main and tests. */
import { lazy, Suspense } from "react";
import { createBrowserRouter, Outlet, type RouteObject } from "react-router-dom";
import EmptyState from "./components/EmptyState";
import Skeleton from "./components/Skeleton";
import DashboardLayout from "./layouts/DashboardLayout";

const Home = lazy(() => import("./pages/Home"));
const History = lazy(() => import("./pages/History"));
const Statistics = lazy(() => import("./pages/Statistics"));

const Heatmaps = lazy(() => import("./pages/Heatmaps"));
const Trends = lazy(() => import("./pages/Trends"));
const MonteCarlo = lazy(() => import("./pages/MonteCarlo"));
const Networks = lazy(() => import("./pages/Networks"));
const AI = lazy(() => import("./pages/IA"));
const Models = lazy(() => import("./pages/Models"));
const Experiments = lazy(() => import("./pages/Experiments"));
const Backtesting = lazy(() => import("./pages/Backtesting"));
const DeepLearning = lazy(() => import("./pages/DL"));
const MisNumeros = lazy(() => import("./pages/MisNumeros"));

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
      { path: "dl", element: <DeepLearning /> },
      { path: "numeros", element: <MisNumeros /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
