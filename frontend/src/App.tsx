import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import ImportPage from './pages/ImportPage';
import DashboardPage from './pages/DashboardPage';
import DaysListPage from './pages/DaysListPage';
import DayViewPage from './pages/DayViewPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ImportPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/days" element={<DaysListPage />} />
        <Route path="/days/:day" element={<DayViewPage />} />
      </Routes>
    </Layout>
  );
}
