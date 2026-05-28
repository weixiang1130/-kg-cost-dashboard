// App 殼 — 路由 + Sidebar 導航
const { useState: useStateApp } = React;

const PAGES = {
  home: PageHome,
  batch: PageBatch,
  assumption: PageAssumption,
  cost: PageCost,
  prediction: PagePrediction,
  history: PageHistory,
};

function App() {
  const [page, setPage] = useStateApp('home');
  const Page = PAGES[page] || PageHome;

  return (
    <div className="app-layout">
      <Sidebar page={page} setPage={setPage}/>
      <main className="main-content">
        <Page setPage={setPage}/>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
