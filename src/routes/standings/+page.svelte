<script>
	// Custom VP standings: 6 VP per H2H win + 1 VP per non-opponent outscored.
	// Data comes from /custom-standings.json, which the "Update Sleeper standings"
	// GitHub Action rewrites every week (see sleeper-standings/ in the repo).
	import { onMount } from 'svelte';

	let data = null;
	let error = null;

	const rec = (w, l, t) => `${w}-${l}${t ? `-${t}` : ''}`;
	const pts = (n) => Number(n).toFixed(2);

	onMount(async () => {
		try {
			const res = await fetch('/custom-standings.json', { cache: 'no-store' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			data = await res.json();
		} catch (e) {
			error = e.message;
		}
	});

	$: through = data?.weeks?.length ? `Through week ${data.weeks[data.weeks.length - 1]}` : 'No completed weeks yet';
	$: rules = data
		? `${data.scoring.h2h_win} VP per head-to-head win, plus ${data.scoring.non_opponent_win} VP for each other team you outscore that week`
		: '';
</script>

<svelte:head>
	<title>Standings</title>
</svelte:head>

<div class="standings-page">
	<h1>{data?.season ? `${data.season} Standings` : 'Standings'}</h1>

	{#if error}
		<p class="note">Standings couldn't load ({error}). Run the "Update Sleeper standings" workflow on GitHub to create them.</p>
	{:else if !data}
		<p class="note">Loading standings…</p>
	{:else}
		<p class="note">{through}. {rules}.</p>

		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="num">#</th>
						<th class="team-col">Team</th>
						<th class="num vp">VP</th>
						<th class="num">H2H</th>
						<th class="num">Non-opp</th>
						<th class="num">PF</th>
						<th class="num">PA</th>
					</tr>
				</thead>
				<tbody>
					{#each data.standings as t (t.roster_id)}
						<tr>
							<td class="num rank">{t.rank}</td>
							<td class="team-col">
								<div class="team">
									{#if t.avatar}
										<img src={t.avatar} alt="" width="32" height="32" loading="lazy" />
									{:else}
										<span class="avatar-blank" aria-hidden="true">{t.team.charAt(0)}</span>
									{/if}
									<div>
										<div class="team-name">{t.team}</div>
										<div class="manager">{t.manager}</div>
									</div>
								</div>
							</td>
							<td class="num vp">{t.custom_points}</td>
							<td class="num">{rec(t.h2h_wins, t.h2h_losses, t.h2h_ties)}</td>
							<td class="num">{rec(t.non_opp_wins, t.non_opp_losses, t.non_opp_ties)}</td>
							<td class="num">{pts(t.points_for)}</td>
							<td class="num">{pts(t.points_against)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<p class="updated">Updated {data.updated}. Ties in VP are broken by points for.</p>
	{/if}
</div>

<style>
	.standings-page {
		max-width: 860px;
		margin: 0 auto;
		padding: 1.5rem 1rem 3rem;
	}

	h1 {
		margin: 0 0 0.25rem;
		text-align: center;
	}

	.note {
		text-align: center;
		margin: 0 auto 1.5rem;
		max-width: 60ch;
		opacity: 0.8;
	}

	.table-wrap {
		overflow-x: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
	}

	th,
	td {
		padding: 0.6rem 0.5rem;
		border-bottom: 1px solid color-mix(in srgb, currentColor 15%, transparent);
		white-space: nowrap;
	}

	th {
		font-size: 0.85rem;
		font-weight: 600;
		opacity: 0.75;
		border-bottom-width: 2px;
	}

	.num {
		text-align: right;
	}

	.team-col {
		text-align: left;
		width: 100%;
	}

	.rank {
		opacity: 0.6;
	}

	.vp {
		font-weight: 700;
		font-size: 1.05rem;
	}

	.team {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}

	.team img,
	.avatar-blank {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		flex-shrink: 0;
		object-fit: cover;
	}

	.avatar-blank {
		display: grid;
		place-items: center;
		font-weight: 700;
		background: color-mix(in srgb, currentColor 12%, transparent);
	}

	.team-name {
		font-weight: 600;
	}

	.manager {
		font-size: 0.8rem;
		opacity: 0.65;
	}

	.updated {
		text-align: center;
		font-size: 0.8rem;
		opacity: 0.6;
		margin-top: 1rem;
	}

	@media (max-width: 600px) {
		th,
		td {
			padding: 0.5rem 0.35rem;
			font-size: 0.85rem;
		}
		.manager {
			display: none;
		}
	}
</style>
