import { AppShell } from "./components/layout/AppShell";
import { BoltSelection } from "./pages/BoltSelection";
import { JointGeometry } from "./pages/JointGeometry";
import { Loading } from "./pages/Loading";
import { Results } from "./pages/Results";
import { Report } from "./pages/Report";
import { useAppStore } from "./store/useAppStore";

export default function App() {
  const { currentStep } = useAppStore();

  const pages = [
    <BoltSelection key="bolt" />,
    <JointGeometry key="joint" />,
    <Loading key="loading" />,
    <Results key="results" />,
    <Report key="report" />,
  ];

  return (
    <AppShell>
      {pages[currentStep]}
    </AppShell>
  );
}
