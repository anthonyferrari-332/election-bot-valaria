import os
BOT_TOKEN = os.getenv('BOT_TOKEN')

import discord
from discord import app_commands
from discord.ext import commands

bot = commands.Bot(command_prefix="elect!", intents=discord.Intents.all(), help_command=None)
started = False

election_state = {
    'active': False,
    'name': None,
    'vote_amount': 1,
    'candidates': [],
    'votes': {},
    'voters': {}
}

approved_admin_ids = [708867559490846730]  # replace with real admin user IDs

def citizen_role_check(member: discord.Member) -> bool:
    return any(role.name.lower() == 'citizen' or role.name.lower() == 'resident' for role in member.roles)

def is_admin(member: discord.Member) -> bool:
    return member.id in approved_admin_ids

class VoteSelect(discord.ui.Select):
    def __init__(self, voter_id: int):
        options = [discord.SelectOption(label=candidate, value=candidate)
                   for candidate in election_state['candidates']]
        super().__init__(
            placeholder='Pick your candidate(s)',
            min_values=1,
            max_values=min(len(options), election_state['vote_amount']),
            options=options,
        )
        self.voter_id = str(voter_id)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.voter_id:
            await interaction.response.send_message('This ballot is not for you.', ephemeral=True)
            return

        if not election_state['active']:
            await interaction.response.edit_message(content='The election is no longer active.', view=None)
            return

        selected = set(self.values)
        previous_votes = set(election_state['voters'].get(self.voter_id, []))

        for candidate in previous_votes - selected:
            election_state['votes'][candidate] -= 1
        for candidate in selected - previous_votes:
            election_state['votes'][candidate] = election_state['votes'].get(candidate, 0) + 1

        election_state['voters'][self.voter_id] = list(selected)

        for child in self.view.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f'Your secret ballot has been recorded for {len(selected)} candidate(s).',
            view=self.view,
        )

class VoteView(discord.ui.View):
    def __init__(self, voter_id: int):
        super().__init__(timeout=300)
        self.add_item(VoteSelect(voter_id))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

async def startup():
    channel = bot.get_channel(1515567713852985386)
    if channel is not None:
        await channel.send('lets get voting!')
    else:
        print('lets get voting!')

@bot.event
async def on_ready():
    global started
    if not started:
        await startup()
        started = True
    print(f'Logged in as {bot.user.name}...What\'s up!')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.command(name='createelection')
async def createelection(ctx, *, election_name: str):
    if ctx.guild is None:
        await ctx.send('Create elections from a server channel, not in DMs.')
        return

    if not is_admin(ctx.author):
        await ctx.reply('You do not have permission to manage elections.', mention_author=True)
        return

    if election_state['active']:
        await ctx.send('There is already an active election. Close it before creating a new one.')
        return

    parts = [part.strip() for part in election_name.split(',', 1)]
    name = parts[0]
    vote_amount = 1

    if len(parts) > 1 and parts[1]:
        try:
            vote_amount = max(1, int(parts[1].strip()))
        except ValueError:
            await ctx.reply('Vote amount must be a number. Use: elect!createelection <name>, <vote_amount>', mention_author=True)
            return

    if not name:
        await ctx.reply('Election name cannot be empty.', mention_author=True)
        return

    election_state['active'] = True
    election_state['name'] = name
    election_state['vote_amount'] = vote_amount
    election_state['candidates'] = []
    election_state['votes'] = {}
    election_state['voters'] = {}

    await ctx.reply(
        f"Election created: **{election_state['name']}** with up to {election_state['vote_amount']} vote(s) per voter. Add candidates with elect!addcandidate <name>.",
        mention_author=True,
    )

@bot.command(name='addcandidate')
async def addcandidate(ctx, *, candidate_name: str):
    if ctx.guild is None:
        await ctx.reply('Add candidates from a server channel, not in DMs.', mention_author=True)
        return

    if not is_admin(ctx.author):
        await ctx.reply('You do not have permission to manage elections.', mention_author=True)
        return

    if not election_state['active']:
        await ctx.reply('No active election. Create one first with elect!createelection <name>.', mention_author=True)
        return

    name = candidate_name.strip()
    if not name:
        await ctx.reply('Candidate name cannot be empty.', mention_author=True)
        return

    if name.lower() in (c.lower() for c in election_state['candidates']):
        await ctx.reply(f'Candidate **{name}** is already in the election.', mention_author=True)
        return

    election_state['candidates'].append(name)
    election_state['votes'][name] = 0
    await ctx.reply(f'Candidate **{name}** has been added to the election.', mention_author=True)

@bot.command(name='vote')
async def vote(ctx):
    if not election_state['active']:
        await ctx.reply('No active election to vote in.', mention_author=True)
        return

    if not isinstance(ctx.author, discord.Member):
        await ctx.reply('You must use this command from a server so your Resident or Citizen role can be checked.', mention_author=True)
        return

    if not citizen_role_check(ctx.author):
        await ctx.reply('You must be a resident or citizen to vote.', mention_author=True)
        return

    if str(ctx.author.id) in election_state['voters']:
        await ctx.reply('You have already voted!', mention_author=True)
        return

    if not election_state['candidates']:
        await ctx.reply('There are no candidates in the current election.', mention_author=True)
        return

    view = VoteView(ctx.author.id)
    try:
        await ctx.author.send(
            f"Secret ballot for election **{election_state['name']}**. Select up to {election_state['vote_amount']} candidate(s).",
            view=view,
        )
    except discord.Forbidden:
        await ctx.reply('Unable to DM you. Please open your DMs and try again.', mention_author=True)
        return

    await ctx.reply('Please check your DMs for your ballot.', mention_author=True)

@bot.command(name='electionstatus')
async def electionstatus(ctx):
    if not election_state['active']:
        await ctx.reply('There is no active election right now.', mention_author=True)
        return

    if not ctx.guild:
        await ctx.reply('Election status must be requested from a server channel.', mention_author=True)
        return

    if not election_state['candidates']:
        await ctx.reply('The election is active, but no candidates have been added yet.', mention_author=True)
        return

    eligible_members = [member for member in ctx.guild.members if citizen_role_check(member)]
    eligible_count = len(eligible_members)
    total_votes = len(election_state['voters'])
    turnout = (total_votes / eligible_count * 100) if eligible_count else 0.0
    turnout_text = f"{turnout:.2f}%"

    if is_admin(ctx.author):
        lines = [f"Election: **{election_state['name']}**"]
        lines.append('Candidates and current vote counts:')
        for candidate in election_state['candidates']:
            lines.append(f"- **{candidate}**: {election_state['votes'].get(candidate, 0)} votes")
        lines.append(f"Total votes cast: {total_votes}")
        lines.append(f"Turnout: {turnout_text}")
        await ctx.reply('\n'.join(lines), mention_author=True)
    else:
        await ctx.reply(
            f"Election: **{election_state['name']}**\n"
            f"Total votes cast: {total_votes}\n"
            f"Turnout: {turnout_text}",
            mention_author=True,
        )

@bot.command(name='closeelection')
async def closeelection(ctx):
    if not election_state['active']:
        await ctx.reply('There is no active election to close.', mention_author=True)
        return

    if not is_admin(ctx.author):
        await ctx.reply('You do not have permission to manage elections.', mention_author=True)
        return

    if not election_state['candidates']:
        election_state['active'] = False
        await ctx.reply('Election closed with no candidates.', mention_author=True)
        return

    winners_sorted = sorted(election_state['votes'].items(), key=lambda item: item[1], reverse=True)
    winner_count = min(election_state['vote_amount'], len(winners_sorted))
    threshold = winners_sorted[winner_count - 1][1] if winner_count > 0 else 0
    winners = [candidate for candidate, count in winners_sorted if count >= threshold and count > 0]

    result_lines = [f"Election **{election_state['name']}** closed."]
    result_lines.append(f"Total votes cast: {len(election_state['voters'])}")
    result_lines.append('Final tallies:')
    for candidate in election_state['candidates']:
        result_lines.append(f"- **{candidate}**: {election_state['votes'].get(candidate, 0)}")

    if not winners:
        result_lines.append('No votes were cast.')
    else:
        result_lines.append(
            f"Top {election_state['vote_amount']} winner(s): {', '.join('**' + w + '**' for w in winners)} with {threshold} vote(s) or more."
        )

    election_state['active'] = False
    election_state['name'] = None
    election_state['vote_amount'] = 1
    election_state['candidates'] = []
    election_state['votes'] = {}
    election_state['voters'] = {}

    await ctx.reply('\n'.join(result_lines), mention_author=True)

@bot.command(name='help')
async def help_command(ctx):
    help_text = (
        '**Election Bot Commands**\n'
        '`elect!createelection <name>, <vote_amount>` - Start a new election.\n'
        '`elect!addcandidate <candidate>` - Add a candidate to the active election.\n'
        '`elect!vote` - Receive your private ballot in DMs. Requires you to be a resident or citizen.\n'
        '`elect!electionstatus` - Show the current election and vote counts.\n'
        '`elect!closeelection` - End the election and announce the winner(s).\n'
        '`elect!help` - Show this help message.'
    )
    await ctx.reply(help_text, mention_author=True)

bot.run(BOT_TOKEN)
