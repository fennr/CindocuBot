import disnake
from disnake.ext import commands
import peewee

from src.database.models import (Members, Likes, Relationships,
                                 RelationshipParticipant)
from src.formatters import ordered_list
from src.custom_errors import UsedNotOnGuild
from src.discord_views.embeds import DefaultEmbed
from src.utils.slash_shortcuts import only_guild
from src.utils.experience import format_exp
from src.utils.time_ import display_time
from src.ext.economy.services import get_economy_settings
from src.translation import get_translator
from src.discord_views.base_view import BaseView
from src.logger import get_logger
from src.bot import SEBot


logger = get_logger()
t = get_translator(route="ext.top")
TOP_SIZE = 10


class TopCog(commands.Cog):
    def __init__(self, bot: SEBot):
        self.bot = bot

    @commands.slash_command(**only_guild)
    async def top(
        self,
        inter: disnake.ApplicationCommandInteraction,
    ):
        """
        Посмотреть топы участников этого сервера
        """
        guild = inter.guild
        if not guild:
            raise UsedNotOnGuild()

        view = TopView(guild_id=guild.id)
        await view.start_from(inter)


class TopView(BaseView):
    def __init__(self, guild_id: int) -> None:
        super().__init__()
        self.guild_id = guild_id
        self.top_map = {
            t('top_select_voice'): create_voice_top_embed,
            t('top_select_balance'): create_balance_top_embed,
            t('top_select_reputation'): create_reputation_top_embed,
            t('top_select_experience'): create_experience_top_embed,
            t('top_select_relationship'): create_relationships_top_embed,
        }
        self.add_item(TopSelect(self.top_map))

    async def _response(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.send_message(
            embed=list(self.top_map.values())[0](self.guild_id),
            view=self,
        )


class TopSelect(disnake.ui.Select):
    view: TopView

    def __init__(self, top_map):
        options = [
            disnake.SelectOption(
                label=name,
            ) for name in top_map
        ]
        super().__init__(options=options)

    async def callback(
        self,
        interaction: disnake.MessageInteraction,
        /
    ) -> None:
        name = self.values[0]
        await interaction.response.edit_message(
            embed=self.view.top_map[name](self.view.guild_id),
            view=self.view,
        )


def _build_members_top_query(
    guild_id: int,
    ordering: peewee.Ordering
):
    return (
        Members.
        select(Members).
        where(Members.guild_id == guild_id).
        order_by(ordering).  # type: ignore
        limit(TOP_SIZE)
    )


def _build_voice_top_query(guild_id: int):
    return _build_members_top_query(
        guild_id=guild_id,
        ordering=-Members.voice_activity,
    )


def _build_balance_top_query(guild_id: int):
    return _build_members_top_query(
        guild_id=guild_id,
        ordering=-Members.balance,
    )


def _build_experience_top_query(guild_id: int):
    return _build_members_top_query(
        guild_id=guild_id,
        ordering=-Members.experience,
    )


def _build_reputation_top_query(guild_id: int):
    reputation_sum = peewee.fn.COALESCE(peewee.fn.sum(Likes.type), 0)
    return (
        Members.select(
            Members.user_id,
            reputation_sum.alias('reputation'),
        ).
        join(
            Likes,
            join_type=peewee.JOIN.LEFT_OUTER,
            on=Members.user_id == Likes.to_user_id
        ).
        where(Members.guild_id == guild_id).  # type: ignore
        order_by(peewee.SQL('reputation DESC')).
        group_by(Members.user_id).
        limit(TOP_SIZE)
    )


def _build_relations_top_query(guild_id: int):
    return (
        Relationships.select(
            Relationships.creation_time,
            RelationshipParticipant.user_id,
        ).join(RelationshipParticipant).
        where(Relationships.guild_id == guild_id).  # type: ignore
        order_by(Relationships.creation_time).
        limit(TOP_SIZE * 2)
    )


def create_voice_top_embed(guild_id: int) -> disnake.Embed:
    query = _build_voice_top_query(guild_id)
    desc = ordered_list(
        query,
        lambda item: f'<@{item.user_id}> — {display_time(item.voice_activity)}'  # noqa
    )
    return DefaultEmbed(
        title=t('top_voice'),
        description=desc,
    )


def create_experience_top_embed(guild_id: int) -> disnake.Embed:
    query = _build_experience_top_query(guild_id)
    desc = ordered_list(
        query,
        lambda item: f'<@{item.user_id}> — {format_exp(item.experience)}'  # noqa
    )
    return DefaultEmbed(
        title=t('top_experience'),
        description=desc,
    )


def create_balance_top_embed(guild_id: int) -> disnake.Embed:
    query = _build_balance_top_query(guild_id)
    settings = get_economy_settings(guild_id)
    desc = ordered_list(
        query,
        lambda item: f'<@{item.user_id}> — {item.balance} {settings.coin}'
    )
    return DefaultEmbed(
        title=t('top_balance'),
        description=desc,
    )


def create_reputation_top_embed(guild_id: int) -> disnake.Embed:
    query = _build_reputation_top_query(guild_id)
    desc = ordered_list(
        query,
        lambda item: f'<@{item.user_id}> — {item.reputation} :revolving_hearts:'  # noqa
    )
    return DefaultEmbed(
        title=t('top_reputation'),
        description=desc,
    )


def create_relationships_top_embed(guild_id: int) -> disnake.Embed:
    items = _build_relations_top_query(guild_id).execute()
    items = [(items[i:i + 2]) for i in range(0, len(items), 2)]

    def formatter(item) -> str:
        first_user = f'<@{item[0].relationshipparticipant.user_id}>'
        second_user = f'<@{item[1].relationshipparticipant.user_id}>'
        timestamp = disnake.utils.format_dt(item[0].creation_time, 'f')
        return t(
            'relationship_repr',
            first_user=first_user,
            second_user=second_user,
            timestamp=timestamp,
        )

    desc = ordered_list(items, formatter)
    return DefaultEmbed(
        title=t('top_relationship'),
        description=desc,
    )


def setup(bot):
    bot.add_cog(TopCog(bot))
