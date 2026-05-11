import { BrowserRouter, Routes, Route } from "react-router-dom";

import MainPage from "./pages/Main.jsx";
import TestPage from "./pages/Test.jsx";
import BulkSimulator from "./pages/BulkSimulator.jsx";
import Metrics from "./pages/Metrics.jsx";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainPage />} />
        <Route path="/test" element={<TestPage />} />
        <Route path="/bulk" element={<BulkSimulator />} />
        <Route path="/metrics" element={<Metrics />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;