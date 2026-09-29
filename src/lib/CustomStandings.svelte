<script>
	// Custom VP standings table. Reads the file the "Update Sleeper standings"
	// GitHub Action writes each week.
	//   <CustomStandings />          full table
	//   <CustomStandings compact />  short version for the home page
	import { onMount } from 'svelte';

	export let compact = false;

	const SOURCE =
		'https://raw.githubusercontent.com/luisgonzalez0205-art/league-of-bald/master/static/custom-standings.json';

	let data = null;
	let error = null;

	const rec = (w, l, t) => `${w}-${l}${t ? `-${t}` : ''}`;

	onMount(async () => {
		try {
			const res = await fetch(SOURCE, { cache: 'no-store' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			data = await res.json();
		} catch (e) {
			error = e.message;
		}
	});

	$: lastWeek = data?.weeks?.length ? data.weeks[data.weeks.length - 1] : null;
</script>

<section class="custom-standings" class:compact>
	<h2>Standings</h2>

	{#if error}
		<p class="note">Standings couldn't load ({error}).</p>
	{:else if !data}
		<p class="note">Loading standings…</p>
	{:else}
		<p class="note">
			{lastWeek ? `Through week ${lastWeek}` : 'No completed weeks yet'}.
			{data.scoring.h2h_win} VP per win, {data.scoring.non_opponent_win} VP per other team outscored.
		</p>

		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="num">#</th>
						<th class="team-col">Team</th>
						<th class="num">VP</th>
						<th class="num">H2H</th>
						{#if !compact}
							<th class="num">Non-opp</th>
							<th class="num">PF</th>
							<th class="num">PA</th>
						{/if}
					</tr>
				</thead>
				<tbody>
					{#each data.standings as t (t.roster_id)}
						<tr>
							<td class="num rank">{t.rank}</td>
							<td class="team-col">
								<div class="team">
									{#if t.avatar}
										<img src={t.avatar} alt="" width="28" height="28" loading="lazy" />
									{:else}
										<span class="avatar-blank" aria-hidden="true">{t.team.charAt(0)}</span>
									{/if}
									<div>
										<div class="team-name">{t.team}</div>
										{#if !compact}<div class="manager">{t.manager}</div>{/if}
									</div>
								</div>
							</td>
							<td class="num vp">{t.custom_points}</td>
							<td class="num">{rec(t.h2h_wins, t.h2h_losses, t.h2h_ties)}</td>
							{#if !compact}
								<td class="num">{rec(t.non_opp_wins, t.non_opp_losses, t.non_opp_ties)}</td>
								<td class="num">{Number(t.points_for).toFixed(2)}</td>
								<td class="num">{Number(t.points_against).toFixed(2)}</td>
							{/if}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		{#if compact}
			<p class="more"><a href="/standings">See full standings</a></p>
		{:else}
			<p class="note small">Updated {data.updated}. Ties in VP are broken by points for.</p>
		{/if}
	{/if}
</section>

<style>
	.custom-standings {
		max-width: 860px;
		margin: 0 auto 2rem;
		padding: 0 1rem;
	}

	.compact {
		max-width: 520px;
	}

	h2 {
		text-align: center;
		margin: 1rem 0 0.25rem;
	}

	.note {
		text-align: center;
		margin: 0 auto 1rem;
		max-width: 60ch;
		opacity: 0.8;
	}

	.small {
		font-size: 0.8rem;
		margin-top: 1rem;
		opacity: 0.6;
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
		padding: 0.5rem 0.45rem;
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
	}

	.team {
		display: flex;
		align-items: center;
		gap: 0.55rem;
	}

	.team img,
	.avatar-blank {
		width: 28px;
		height: 28px;
		border-radius: 50%;
		flex-shrink: 0;
		object-fit: cover;
	}

	.avatar-blank {
		display: grid;
		place-items: center;
		font-weight: 700;
		font-size: 0.8rem;
		background: color-mix(in srgb, currentColor 12%, transparent);
	}

	.team-name {
		font-weight: 600;
	}

	.manager {
		font-size: 0.8rem;
		opacity: 0.65;
	}

	.more {
		text-align: center;
		margin-top: 0.75rem;
	}

	@media (max-width: 600px) {
		th,
		td {
			padding: 0.45rem 0.3rem;
			font-size: 0.85rem;
		}
		.manager {
			display: none;
		}
	}
</style>
