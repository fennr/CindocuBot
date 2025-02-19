import logging
from typing import Literal

import disnake
from disnake.ext import commands

from src.custom_errors import CannotUseTwice
from src.ext.reputation.services import change_reputation
from src.discord_views.embeds import DefaultEmbed
from src.converters import interacted_member
from src.utils.slash_shortcuts import only_guild
from src.translation import get_translator
from src.bot import SEBot


loger = logging.getLogger('Arctic')
t = get_translator(route="ext.reputation")
REPUTATION_ACTION_MAP: dict[str, Literal[1, -1, 0]] = {
    'increase': 1,
    'decrease': -1,
    'reset': 0,
}


class ReputationCog(commands.Cog):
    def __init__(self, bot: SEBot):
        self.bot = bot

    @commands.slash_command(**only_guild)
    async def reputation(
        self,
        inter: disnake.ApplicationCommandInteraction,
        member=commands.Param(converter=interacted_member),
        action=commands.Param(choices=[
            'increase', 'decrease', 'reset'
        ]),
    ) -> None:
        """
        Изменить репутацию пользователю

        Parameters
        ----------
        member: Пользователь, которому будет изменена репутация
        action: Увеличить, уменьшить или отменить
        """
        action = REPUTATION_ACTION_MAP[action]
        author_id = inter.author.id
        guild_id = inter.guild.id  # type: ignore
        target_id = member.id
        changed = change_reputation(
            guild_id, author_id, target_id, action,
        )

        if not changed:
            raise CannotUseTwice()

        if action == 1:
            embed = disnake.Embed(
                title=t("increase_title"),
                description=t("increase_desc", author_id=author_id,
                              target_id=target_id),
                color=disnake.Colour.green())
        elif action == -1:
            embed = disnake.Embed(
                title=t("decrease_title"),
                description=t("decrease_desc", author_id=author_id,
                              target_id=target_id),
                color=disnake.Colour.red())
        else:
            embed = DefaultEmbed(
                title=t("reset_title"),
                description=t("reset_desc", author_id=author_id,
                              target_id=target_id),
            )
        embed.set_thumbnail(url=await self.bot.save_avatar(inter.author))
        await inter.response.send_message(
            embed=embed,
        )


def setup(bot):
    bot.add_cog(ReputationCog(bot))
