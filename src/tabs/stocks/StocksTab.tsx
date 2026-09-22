import { useParams } from "react-router-dom";
import { useStocksStore } from "@/store/useStocksStore";
import { TickerTape } from "@/components/ui/TickerTape";
import { PortfolioView } from "./PortfolioView";
import { WatchlistView } from "./WatchlistView";
import { StockInsightsView } from "./StockInsightsView";
import { StockDetailView } from "./StockDetailView";

const VIEWS: Record<string, React.ComponentType> = {
  portfolio: PortfolioView,
  watchlist: WatchlistView,
  insights: StockInsightsView,
};

export function StocksTab() {
  const { subSlug = "portfolio", detailId } = useParams();
  const stocks = useStocksStore((s) => s.stocks);

  const tickerItems = stocks.map((s) => ({ ticker: s.ticker, price: s.price, chg: s.chg }));

  if (detailId) {
    return (
      <div>
        <TickerTape items={tickerItems} />
        <StockDetailView ticker={detailId} backTo={`/stocks/${subSlug}`} />
      </div>
    );
  }

  const View = VIEWS[subSlug] ?? PortfolioView;

  return (
    <div>
      <TickerTape items={tickerItems} />
      <View />
    </div>
  );
}
