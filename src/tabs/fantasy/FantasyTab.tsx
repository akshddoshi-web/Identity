import { useParams } from "react-router-dom";
import { LobbyView } from "./LobbyView";
import { MatchupView } from "./MatchupView";
import { MyTeamView } from "./MyTeamView";
import { LedgerView } from "./LedgerView";
import { DraftBoardView } from "./DraftBoardView";

const VIEWS: Record<string, React.ComponentType> = {
  lobby: LobbyView,
  matchup: MatchupView,
  "my-team": MyTeamView,
  ledger: LedgerView,
};

export function FantasyTab() {
  const { subSlug = "lobby", detailId } = useParams();

  if (subSlug === "lobby" && detailId === "draft") {
    return <DraftBoardView />;
  }

  const View = VIEWS[subSlug] ?? LobbyView;
  return <View />;
}
