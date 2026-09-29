import { leagueID, managers } from '$lib/utils/leagueInfo';
import { get } from 'svelte/store';
import { teamManagersStore } from '$lib/stores';
import { waitForAll } from './multiPromise';
import { getManagers, getTeamData } from './universalFunctions';
import { getLeagueData } from './leagueData';

// Old Sleeper accounts that belong to the same person as a newer account.
// Format: 'old user_id': 'current user_id'
const accountAliases = {
    '76447455113527296': '1263720098858799104', // nickgenova -> rickrenova
};
const mainID = (id) => accountAliases[id] ?? id;

export const getLeagueTeamManagers = async () => {
    if(get(teamManagersStore) && get(teamManagersStore).currentSeason) {
		return get(teamManagersStore);
	}
    let currentLeagueID = leagueID;
	let teamManagersMap = {};
    let finalUsers = {};
    let currentSeason = null;

    // loop through all seasons and create a [year][roster_id]: team, managers object
	while(currentLeagueID && currentLeagueID != 0) {
		const [usersRaw, leagueData, rostersRaw] = await waitForAll(
            fetch(`https://api.sleeper.app/v1/league/${currentLeagueID}/users`, {compress: true}),
			getLeagueData(currentLeagueID),
            fetch(`https://api.sleeper.app/v1/league/${currentLeagueID}/rosters`, {compress: true}),
        ).catch((err) => { console.error(err); });

        const [users, rosters] = await waitForAll(
            usersRaw.json(), 
            rostersRaw.json(), 
        ).catch((err) => { console.error(err); });

        // Merge old accounts into the person's current account
        for(const user of users) {
            user.user_id = mainID(user.user_id);
        }
        for(const roster of rosters) {
            roster.owner_id = mainID(roster.owner_id);
            if(roster.co_owners) {
                roster.co_owners = roster.co_owners.map(mainID);
            }
        }

        const year = parseInt(leagueData.season);
        currentLeagueID = leagueData.previous_league_id;
        if(!currentSeason) {
            currentSeason = year;
        }
        teamManagersMap[year] = {};
        const processedUsers = processUsers(users);

        // in order to not overwrite most recent data, only add new entries to finalUsers
        for(const processedUserKey in processedUsers) {
            if(finalUsers[processedUserKey]) continue;
            finalUsers[processedUserKey] = processedUsers[processedUserKey];
        }
        for(const roster of rosters) {
            teamManagersMap[year][roster.roster_id] = {
                team: getTeamData(processedUsers, roster.owner_id),
                managers: getManagers(roster, processedUsers),
            };
        }
    }
    const response = {
        currentSeason,
        teamManagersMap,
        users: finalUsers,
    }
    teamManagersStore.update(() => response);
    return response;
}

const processUsers = (rawUsers) => {
	let finalUsers = {};
	for(const user of rawUsers) {
        user.user_name = user.user_name ?? user.display_name;
		finalUsers[user.user_id] = user;
        const manager = managers.find(m => m.managerID === user.user_id);
