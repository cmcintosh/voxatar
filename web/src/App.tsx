import { Routes, Route } from "react-router-dom";
import CallPage from "./pages/CallPage";
import Dashboard from "./pages/Dashboard";
import CallDetail from "./pages/CallDetail";
import KnowledgeBase from "./pages/KnowledgeBase";
import AgentConfig from "./pages/AgentConfig";
import Layout from "./components/Layout";

export default function App() {
  return (
    <Routes>
      {/* Call interface — light theme, no sidebar */}
      <Route path="/" element={<CallPage />} />
      <Route path="/c/:slug" element={<CallPage />} />

      {/* Dashboard pages — dark theme with sidebar */}
      <Route
        path="/dashboard"
        element={
          <Layout>
            <Dashboard />
          </Layout>
        }
      />
      <Route
        path="/calls/:id"
        element={
          <Layout>
            <CallDetail />
          </Layout>
        }
      />
      <Route
        path="/knowledge"
        element={
          <Layout>
            <KnowledgeBase />
          </Layout>
        }
      />
      <Route
        path="/settings"
        element={
          <Layout>
            <AgentConfig />
          </Layout>
        }
      />
    </Routes>
  );
}