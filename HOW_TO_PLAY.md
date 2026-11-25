# How to Play

A short guide for anyone who has never played a role-playing game. Reading it takes about five minutes.

**Start a game** from the project folder:

```
python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 12345
```

"The Cellar Rats" is a good first game: one short fight and a few people to talk to. You can show this guide again at any time with `python -m adm.cli guide`, or type `/help` during a game for the short version.

## 1. What is this game?

A **role-playing game** is a story you play. You decide what one character does, and someone else describes the world and what happens next. That someone is called the **Dungeon Master**: they set the scene, play everyone you meet, and say how things turn out.

Here the Dungeon Master is split in two:

- **An AI narrates.** It writes the descriptions and the dialogue. The title of every game is marked "Narrated by AI".
- **A rules engine keeps score.** It decides what actually happens (whether an attack lands, how much health is left, what you carry) and the AI describes that result. The AI cannot change the game on its own.

The rules are a small set inspired by tabletop fantasy role-playing games. You do not need to know any of them to start.

## 2. How to play

Type what your character does in plain English, one action at a time, and press Enter. There are no special words to learn. The game opens by telling you who you are and where you stand.

Some things you could type in "The Cellar Rats":

- `I look around the cellar`
- `I draw my sword and attack the nearest rat`
- `I cast Fire Bolt at the other rat`
- `I cast Cure Wounds on myself`
- `I dodge and keep the rat off me`
- `I sneak quietly towards the barrels`
- `I try to roll the heavy barrel aside`
- `I pick up the ledger`
- `I tell the Keeper I will find the missing ledger`

After every turn you see one short line saying what happened ("You hit giant rat 2 with your short sword. Giant rat 2 is wounded."), then the story. Before each input the game also suggests a few things you could try ("You could try: look around").

## 3. Fights

When a fight starts, everyone takes turns in a fixed **turn order**, set when the fight begins. Enemies act on their own turns, and the game tells you what they did.

On **your turn** you do one of three things:

- **attack** with a weapon you carry,
- **cast a spell** (see section 6), or
- **dodge**, which makes you harder to hit until your next turn.

Doing one of these ends your turn. Looking around, sneaking, lifting, using or picking up items, and talking do **not** use up your turn, so you can do them and still act.

There is no map. Everyone in a fight is close enough to reach everyone else, so you never need to move. The dice decide whether an attack hits, and some enemies are harder to hit than others. A fight is won when every enemy is knocked out, and lost if you are.

## 4. Health

Every character has **health**: how much harm they can take. The game describes it in words: healthy, wounded, badly hurt.

- With no health left, a character is **knocked out**, not dead. Nobody dies in this game.
- A knocked-out character cannot act, and **knocked-out enemies cannot be attacked**.
- The healing spell, Cure Wounds, brings a knocked-out character back into the fight.

Type `/status` at any time to see how you and everyone in the fight are doing.

## 5. The three skills

Some things you try are risky, and the dice decide whether you manage them. This is called a **skill check**. There are three skills:

- **strength**: lifting, pushing, forcing things open.
- **perception**: noticing things, such as a sound, a hidden object, or someone watching.
- **stealth**: sneaking and hiding.

Harder tasks have a higher **difficulty**. Sometimes you **have the upper hand**, and the dice are on your side; sometimes **the odds are against you**. The game tells you which. You never choose a skill by name: just say what you do, and the game picks the skill.

## 6. The two spells

Some characters can cast spells. There are only two:

- **Fire Bolt**: a fire attack at one target. It is a spell you can always cast, as often as you like.
- **Cure Wounds**: heals one character, yourself included, and can bring back someone who is knocked out. It uses one **spell charge**, and **charges do not come back** during a game, so save them for when they matter.

`/status` shows how many spell charges you have left.

## 7. When the game asks you to rephrase

Sometimes you will see:

> I couldn't turn that into an action. Could you rephrase it?

It means the game could not match what you typed to something your character can do right now. Your character did not act, and your turn is not used up. Try:

- **One action at a time.** "I attack the rat" rather than "I attack the rat, grab the keys and run".
- **Name who or what.** "I attack giant rat 2" rather than "I attack it". `/status` shows everyone's names.
- **Use what you carry.** `/inventory` lists your items; you cannot attack with a sword you do not have.
- **Pick someone who is still standing.** Knocked-out enemies cannot be attacked.
- **Wait your turn in a fight.** Attacks, spells and dodging only work on your turn.

## 8. Commands

Anything that starts with `/` is a command for the game itself, not for the Dungeon Master. Commands never use your turn, and the AI never sees them.

| Command | What it shows |
|---|---|
| `/help` | what you can type, and these commands |
| `/status` | your health, spell charges and the fight in progress |
| `/inventory` | what you carry |
| `/quests` | your quests and how far along they are |
| `/rules` | the rules in brief |
| `/glossary` | the game's words and what they mean |
| `/quit` | end the game (`/exit` and Ctrl+C do the same) |
