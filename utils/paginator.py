from __future__ import annotations

import discord


class Paginator(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], author_id: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.author_id = author_id
        self.index = 0
        for i, embed in enumerate(self.embeds):
            embed.set_footer(text=f"Page {i + 1}/{len(self.embeds)}")

        if len(embeds) <= 1:
            self.clear_items()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your menu.", ephemeral=True
            )
            return False

        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        self.index = (self.index - 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index])

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index])

    async def start(self, ctx) -> None:
        if hasattr(ctx, "send"):
            await ctx.send(embed=self.embeds[0], view=self)

        else:
            await ctx.send(embed=self.embeds[0], view=self)
