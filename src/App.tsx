import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { TabIndexRedirect } from "@/components/layout/TabIndexRedirect";
import { TabContent } from "@/components/layout/TabContent";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Navigate to="/home/insights" replace />} />
        <Route path=":tabId" element={<TabIndexRedirect />} />
        <Route path=":tabId/:subSlug" element={<TabContent />} />
        <Route path=":tabId/:subSlug/:detailId" element={<TabContent />} />
      </Route>
      <Route path="*" element={<Navigate to="/home/insights" replace />} />
    </Routes>
  );
}
