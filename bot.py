import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
import random
import string

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 遊戲相關變數
cur_game = ""
players = set()
player_numbers = {}  # 存儲玩家數字的字典
player_orders = {}   # 存儲玩家編號的字典（現在存儲字母）
player_guesses = {}  # 新增：存儲每個玩家的排序猜測
game_starter = None  # 存儲發起遊戲的玩家

class NumberButton(Button):
    def __init__(self, number: int):
        super().__init__(
            label="查看我的數字", 
            style=discord.ButtonStyle.primary, 
            custom_id=f"number_button"
        )
        self.number = number

    async def callback(self, interaction: discord.Interaction):
        if interaction.user in players:  # 確認使用者在玩家列表中
            if cur_game:
                await interaction.response.send_message(
                    f"在 {cur_game} 中，你的數字是: {player_numbers[interaction.user.id]}", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"你的數字是: {player_numbers[interaction.user.id]}", 
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "你不在玩家列表中！", 
                ephemeral=True
            )

class NumberView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(NumberButton(0))  # 數字在 player_numbers 中存儲

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="start", description="為所有玩家分配 1-10 的隨機數字")
async def start(interaction: discord.Interaction):
    """為所有玩家分配 1-10 的隨機數字"""
    if not players:
        await interaction.response.send_message("目前沒有玩家！", ephemeral=True)
        return
        
    if len(players) > 10:
        await interaction.response.send_message("玩家數量超過 10 人，無法分配不重複的數字！", ephemeral=True)
        return

    # 生成不重複的隨機數字
    numbers = random.sample(range(1, 11), len(players))
    
    # 建立每個玩家的數字對應
    global player_numbers, player_guesses
    player_numbers = {}
    player_guesses = {}  # 清空之前的猜測
    for player, number in zip(players, numbers):
        player_numbers[player.id] = number

    # 建立單一按鈕的視圖
    view = NumberView()

    await interaction.response.send_message(
        "數字已分配完成！請點擊下方按鈕查看你的數字，並使用 /order 來提交你認為的正確順序", 
        view=view
    )

@bot.tree.command(name="order", description="提交你認為的正確順序")
async def submit_order(interaction: discord.Interaction, order: str):
    """提交你認為的正確順序"""
    if interaction.user not in players:
        await interaction.response.send_message("你不在玩家列表中！", ephemeral=True)
        return
        
    if not player_numbers:
        await interaction.response.send_message("遊戲尚未開始！請等待 /start", ephemeral=True)
        return

    try:
        # 將輸入的字母轉換為大寫並分割
        input_orders = order.upper().split()
        
        if len(input_orders) != len(players):
            await interaction.response.send_message(
                f"輸入的編號數量不正確！應該輸入 {len(players)} 個編號。", 
                ephemeral=True
            )
            return
            
        # 檢查輸入的字母是否有效
        valid_orders = set(string.ascii_uppercase[:len(players)])
        if set(input_orders) != valid_orders:
            await interaction.response.send_message(
                f"輸入的編號無效！請使用 A 到 {string.ascii_uppercase[len(players)-1]} 的編號，且不要重複。", 
                ephemeral=True
            )
            return
            
        # 儲存玩家的猜測
        player_guesses[interaction.user.id] = input_orders
        
        # 檢查是否所有人都已提交
        if len(player_guesses) == len(players):
            # 向提交者發送私人訊息
            await interaction.response.send_message(
                "你的答案已提交！所有玩家都已完成提交，可以使用 /result 查看結果！", 
                ephemeral=True
            )
            # 向頻道發送公告
            await interaction.channel.send(
                "🎉 所有玩家都已提交排序！\n"
                "現在可以使用 /result 來查看結果！"
            )
        else:
            # 還有人未提交時的訊息
            remaining = len(players) - len(player_guesses)
            await interaction.response.send_message(
                f"你的答案已提交！還有 {remaining} 位玩家尚未提交。", 
                ephemeral=True
            )
            
    except Exception as e:
        await interaction.response.send_message(
            "輸入格式錯誤！請輸入空格分隔的字母，例如：C A B", 
            ephemeral=True
        )

@bot.tree.command(name="result", description="公布所有人的排序結果")
async def show_result(interaction: discord.Interaction):
    """公布所有人的排序結果"""
    if not player_numbers:
        await interaction.response.send_message("遊戲尚未開始！")
        return
        
    if not player_guesses:
        await interaction.response.send_message("還沒有人提交排序！")
        return
        
    if len(player_guesses) < len(players):
        await interaction.response.send_message(
            f"還有玩家未提交排序！ ({len(player_guesses)}/{len(players)})"
        )
        return

    # 獲取正確順序
    correct_sequence = sorted(
        [(pid, num) for pid, num in player_numbers.items()], 
        key=lambda x: x[1]
    )
    correct_sequence = [pid for pid, _ in correct_sequence]

    # 檢查每個玩家的答案
    result_message = "遊戲結果：\n\n"
    correct_players = []
    wrong_players = []

    for player_id, guess_orders in player_guesses.items():
        member = interaction.guild.get_member(player_id)
        mention = member.mention if member else f"<@{player_id}>"
        
        # 將字母順序轉換為玩家ID順序
        order_to_pid = {order: pid for pid, order in player_orders.items()}
        guess_sequence = [order_to_pid[order] for order in guess_orders]
        
        # 檢查是否正確
        if guess_sequence == correct_sequence:
            correct_players.append(mention)
        else:
            wrong_players.append(mention)

    # 顯示正確答案
    result_message += "正確順序：\n"
    for i, pid in enumerate(correct_sequence, 1):
        member = interaction.guild.get_member(pid)
        mention = member.mention if member else f"<@{pid}>"
        number = player_numbers[pid]
        result_message += f"{i}. {mention} (編號: {player_orders[pid]}, 數字: {number})\n"

    # 顯示答對和答錯的玩家
    result_message += "\n🎉 答對的玩家：\n"
    result_message += "無" if not correct_players else "\n".join(correct_players)
    
    result_message += "\n\n❌ 答錯的玩家：\n"
    result_message += "無" if not wrong_players else "\n".join(wrong_players)

    await interaction.response.send_message(result_message)

@bot.tree.command(name="game", description="設定目前遊戲名稱")
async def game(interaction: discord.Interaction, game_name: str):
    """設定目前遊戲名稱"""
    global cur_game
    cur_game = game_name
    await interaction.response.send_message(f"已更改目前遊戲為: {game_name}")

@bot.tree.command(name="join", description="加入玩家列表")
async def join(interaction: discord.Interaction):
    """加入玩家列表"""
    global players, player_orders
    player = interaction.user
    
    if player in players:
        await interaction.response.send_message(
            f"{interaction.user.mention} 你已經在玩家列表中了！"
        )
        return
    
    # 加入玩家並自動分配字母編號
    players.add(player)
    # 使用大寫字母 A, B, C, ...
    player_orders[player.id] = string.ascii_uppercase[len(players)-1]
    
    await interaction.response.send_message(
        f"{interaction.user.mention} 已加入玩家列表！\n"
        f"你的編號是: {player_orders[player.id]}\n"
        f"目前玩家數: {len(players)}"
    )

@bot.tree.command(name="leave", description="離開玩家列表")
async def leave(interaction: discord.Interaction):
    """離開玩家列表"""
    global players, player_orders
    player = interaction.user
    
    if player not in players:
        await interaction.response.send_message(
            f"{interaction.user.display_name} 你不在玩家列表中！"
        )
        return
    
    # 移除玩家
    players.remove(player)
    leaving_order = player_orders.pop(player.id)
    
    # 重新調整其他玩家的編號
    for pid in player_orders:
        if player_orders[pid] > leaving_order:
            player_orders[pid] -= 1
    
    await interaction.response.send_message(
        f"{interaction.user.mention} 已離開玩家列表！目前玩家數: {len(players)}"
    )

@bot.tree.command(name="list", description="顯示目前的玩家列表")
async def list_players(interaction: discord.Interaction):
    """顯示目前的玩家列表"""
    if not players:
        await interaction.response.send_message("目前沒有玩家！")
        return
    
    # 根據編號排序顯示玩家列表
    sorted_players = sorted(
        [(pid, order) for pid, order in player_orders.items()],
        key=lambda x: x[1]
    )
    
    player_list = []
    for pid, order in sorted_players:
        member = interaction.guild.get_member(pid)
        if member:
            player_list.append(f"{order}. {member.mention}")
        else:
            player_list.append(f"{order}. <@{pid}>")
    
    formatted_list = "\n".join(player_list)
    await interaction.response.send_message(f"目前玩家列表：\n{formatted_list}")

@bot.tree.command(name="help", description="顯示遊戲說明")
async def help(interaction: discord.Interaction):
    """顯示遊戲說明"""
    help_text = """
遊戲指令說明：
/join - 加入遊戲並獲得字母編號
/leave - 離開遊戲
/list - 顯示玩家列表和編號
/start - 開始遊戲，分配數字
/order [順序] - 提交你認為的正確順序
/result - 公布所有人的排序結果
/clear - 清空遊戲

遊戲流程：
1. 所有玩家使用 /join 加入遊戲
2. 使用 /start 開始遊戲，每個人會收到一個數字
3. 每個玩家使用 /order 提交自己認為的正確順序
4. 所有人都提交後，使用 /result 查看結果

提交順序的方式：
1. 使用 /list 查看所有玩家的編號
2. 根據你認為的正確順序，輸入編號
例如：有3個玩家，你認為編號C應該第一個，編號A第二個，編號B第三個
就輸入：/order C A B

注意：
- 順序中的字母必須是玩家的編號
- 字母之間用空格分隔
- 必須包含所有玩家的編號
- 字母大小寫不敏感
"""
    await interaction.response.send_message(help_text)

@bot.tree.command(name="clear", description="清空玩家列表")
async def clear(interaction: discord.Interaction):
    """清空玩家列表"""
    global players, player_numbers, player_orders, player_guesses
    players.clear()
    player_numbers.clear()
    player_orders.clear()
    player_guesses.clear()
    await interaction.response.send_message("已清空玩家列表！")

bot.run("ENTER YOUR TOKEN")

