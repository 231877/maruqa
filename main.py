import sqlite3, vk_api, time, datetime, threading, math, random, json, re, os, glob, requests
from vk_api.keyboard import VkKeyboard
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

from location import *

commands, token, login, password = [], "token", "login", "password"
admin = ['!отправить', '!забанить', '!инфо']
icons, assoc, Travel = {
	'coins': '&#128176;',
	'energy': '&#9889;',
	'health': '&#10084;',
	'xp': '&#11088;',
	'time': '&#128337;',
	'price': '&#127873;',
	'rating': '&#128302;'
}, {
	'city': 0,
	'tavern': 1,
	'character': 2,
	'inventory': 4,
	'map': 8,
	'forest': 16,
	'desert': 32,
	'swamp': 64,
	'fight': 128,
	'craft': 256,
	'error': 512,
	'travel': 1024,
	'attack': 4096,
	'shield': 8192,
	'opendoor': 16384,
	'traid': 32768,
	'dialog': 65536,
	'nickname': 131072,
	'holiday': 262144,
	'cave': 524288,
	'player': 1048576
}, {}

def find_story(story):
	val = random.randint(0, len(story) - 1)
	text, price, unprice = story[val]['text'] + ' ', None, None
	if 'variable' in story[val]: 
		obj = find_story(story[val]['variable'])
		text += obj[0]
		price, unprice = obj[1], obj[2]
	else:
		if 'price' in story[val]: price = story[val]['price']
		elif 'unprice' in story[val]: unprice = story[val]['unprice']
	return [text, price, unprice]

class Location:
	_list = {}
	def __init__(self, *argv):
		for arg in argv:
			keys, commands, level = [], [], 1
			if 'keyboard' in arg: keys = arg['keyboard']
			if 'commands' in arg: commands = arg['commands']
			if 'level' in arg: level = arg['level']
			self.add(ID=arg['id'], keyboard=keys, level=level, commands=commands)
	def add(self, ID='', keyboard=[], level=1, commands=[]):
		if ID == 'map':
			count = 0
			for row in sorted(Travel, key=lambda i: Travel[i]['time']):
				commands.append(Travel[row]['name'].lower())
				if count < 4: count += 1
				else:
					count = 0
					keyboard.append({'line': 1})
				keyboard.append({'text': Travel[row]['name'], 'color': 'positive'})
			keyboard.append({'line': 1})
			keyboard.append({'text': 'Назад', 'color': 'primary'})
			commands.append('назад')
		self._list[ID] = {
			'keyboard': keyboard,
			'commands': commands,
			'level': level
		}
	def keyboard(self, ID):
		keys = VkKeyboard(one_time=bool(ID is not 'tavern'))
		for key in self._list[ID]['keyboard']:
			if not 'line' in key: keys.add_button(key['text'], color=key['color'])
			else: keys.add_line()
		return keys

class GUI:
	def __init__(self): self.errors, self.print = [], []
	def add_print(self, text='', name=''):
		self.print.append("[{0}]: ".format(datetime.datetime.now().strftime("%H:%M:%S")) + text.replace(name, '\033[92m{0}\033[0m'.format(name)))
		self.render()
	def add_error(self, text=''): 
		self.errors.append("[{0}]: \033[91m".format(datetime.datetime.now().strftime("%H:%M:%S")) + text + '\033[0m')
		self.render()
	def get(self, arr, count=5):
		for i in range(max(len(arr) - count, 0), len(arr)): yield arr[i]
	def render(self):
		os.system('clear')
		print("\033[7mmessages.log\033[0m")
		for i in self.get(self.print, count=20): print(i)
		print("\033[7merrors\033[0m")
		for i in self.get(self.errors, count=20): print(i)

class Check:
	def __init__(self, vk=None, group_id=0): self.vk, self.group_id = vk, group_id
	def member(self, user_id): return self.vk.method('groups.isMember', {'group_id': self.group_id, 'user_id': user_id })
	def admin(self, user_id):
		for user in self.vk.method('groups.getMembers', { 'group_id': self.group_id, 'filter': 'managers' })['items']:
			if str(user_id) == str(user['id']): return True
		return False

class Query:
	def __init__(self, db='db.splite'):
		self.db = sqlite3.connect(db, check_same_thread=False)
		self.cursor = self.db.cursor()
	def many(self, query):
		self.cursor.execute(query)
		return self.cursor.fetchall()
	def one(self, query):
		self.cursor.execute(query)
		return self.cursor.fetchone()
	def save(self, query):
		self.cursor.executescript(query)
		self.db.commit()
	def close(self):
		self.cursor.close()
		self.db.close()

class Translate:
	def barmen(self, text):
		arr = text.split(':')
		if len(arr) > 1:
			arr[0], arr[1] = arr[0].split(), arr[1].split()
			if len(arr[0]) > 2:
				if arr[0][0].lower() == 'бармен' and arr[0][1].lower() == 'передай':
					return {'username': ' '.join(arr[0][2:]), 'message': ' '.join(arr[1])}
		return None
	def text(self, text):
		arr = text.split(' ')
		arr[0] = arr[0].lower()
		if len(arr) > 1:
			if arr[0] in ['создать', 'использовать']: return {'type': arr[0], 'item': ' '.join(arr[1:]), }
			elif arr[0] in ['!отправить', 'продать', '!забанить', '!конкурс']:
				offset, count = 1, 1
				if re.search(r'\d+', arr[1]):
					if re.search(r'[\-\+\.]', arr[1]): return None
					if len(arr[1]) < 5:
						count = int(arr[1])
						offset = 2
					else: return None
				elif re.search(r'[\-\+\.]', arr[1]) and arr[0] != '!отправить': return None
				if ('игроку' in arr) or ('за' in arr):
					for i in range(0, len(arr)):
						if arr[i] == 'за': 
							item, price = ' '.join(arr[offset: i]), arr[i + 1]
							if arr[0] != '!забанить':
								if not re.match(r'[^\.\-\+]\d+', price) or len(price) >= 5: return None
								else: price = int(price)
							else: price = ' '.join(arr[(i + 1):])
						if arr[i] == 'игроку': item, price = ' '.join(arr[offset: i]), ' '.join(arr[(i + 1):])
				else:
					item, price = ' '.join(arr[offset:(len(arr) - 1)]), int(arr[len(arr) - 1])
					if not re.match(r'[^\.\-\+]\d+', str(price)) or len(str(price)) >= 5: return None
				return {
					'type': arr[0],
					'item': item,
					'price': price,
					'count': count
				}
			elif arr[0] in ['страница', 'купить']:
				if re.search(r'\d+', arr[1]):
					if re.search(r'[\-\+\.]', arr[1]): return None
					count = int(arr[1])
				return {'type': arr[0], 'count': count, 'item': ''}
		return None
	def rp(self, message=None, name=None):
		text, arr = message, re.findall(r'\*.+?\*', message)
		if not len(arr): text = "%s сказал: %s"%(name, message)
		elif re.match(r'[^*]', message): text = "%s сказал: %s"%(name, message)
		for row in arr:
			action = re.findall(r'\*(.+)?\*', row)[0]
			if re.match(r'[^*]', action): text = re.sub(r'\*%s\*'%action, "[%s %s]"%(name, action), text)
		return text
	def number(self, value):
		text = str(value)
		if len(text) >= 4 and len(text) <= 5:
			i = len(text) - 3
			if text[i] != '0': return "%s,%sK"%(''.join(text[0:i]), text[i])
			else: return "%sK"%(''.join(text[0:i]))
		elif len(text) == 6: return "%sKK"%(''.join(text[0:3]))
		elif len(text) > 6:
			i = len(text) - 6
			if text[i] != '0': return "%s,%sM"%(''.join(text[0:i]), text[i])
			else: return "%sM"%(''.join(text[0:i]))
		else: return text

class Core:
	def __init__(self, token='', login='', password='',group_id=0):
		def auth(): return input("key code auth: "), True
		def captcha(capt): return capt.try_again(input("captcha code {0}: ".format(capt.get_url()).strip()))
		admin = vk_api.VkApi(login=login, password=password, auth_handler=auth, captcha_handler=captcha, api_version='5.92')
		admin.auth()
		self.session, self.hour, self.vk, self.group_id, self.day = admin.get_api(), datetime.datetime.today().hour, vk_api.VkApi(token=token, api_version='5.92'), group_id, datetime.datetime.today().weekday()
		self.query, self.world, self.check, self.translate = Query(db='db.splite'), Query(db='main.db'), Check(vk=self.vk, group_id=group_id), Translate()
		for row in self.world.many("SELECT `id` FROM `location`"): Travel[row[0]] = self.travel(row[0])
		self.location, self.gui = Location({
			'id': 'character',
			'keyboard': [
				{'text': 'Инвентарь', 'color': 'positive'},
				{'text': 'Мастерская', 'color': 'positive'}, {'line': 1},
				{'text': 'Сменить имя', 'color': 'default'}, {'line': 1},
				{'text': 'Назад', 'color': 'primary'}
			],
			'commands': ['инвентарь', 'мастерская', 'сменить имя', 'назад']
		},{
			'id': 'city',
			'keyboard': [
				{'text': 'Персонаж', 'color': 'primary'},
				{'text': 'Карта', 'color': 'positive'}, {'line': 1},
				{'text': 'Таверна', 'color': 'positive'},
				{'text': 'Арена', 'color': 'negative'},
				{'text': 'Рынок', 'color': 'positive'}
			],
			'commands': ['персонаж', 'карта', 'таверна', 'арена', 'рынок']
		}, {'id': 'map'},
		{
			'id': 'inventory',
			'keyboard': [{'text': 'Назад', 'color': 'primary'}],
			'commands': ['использовать', 'продать', 'назад']
		},{
			'id': 'tavern',
			'keyboard': [
				{'text': 'Бармен', 'color': 'positive'},
				{'text': 'Назад', 'color': 'primary'}
			],
			'commands': ['бармен', 'назад'],
			'level': 5
		}, {
			'id': 'fight',
			'keyboard': [
				{'text': 'Атака', 'color': 'positive'},
				{'text': 'Защита', 'color': 'default'}
			],
			'commands': ['атака', 'защита']
		}, {
			'id': 'craft',
			'keyboard': [
				{'text': 'Страница 2', 'color': 'positive'}, {'line': 1},
				{'text': 'Назад', 'color': 'primary'}
			],
			'commands': ['создать', 'страница', 'назад']
		}, {
			'id': 'traid',
			'keyboard': [
				{'text': 'Персонаж', 'color': 'positive'}, {'line': 1},
				{'text': 'Назад', 'color': 'primary'}
			],
			'commands': ['персонаж', 'страница', 'купить', 'назад']
		}, {
			'id': 'dialog',
			'keyboard': [
				{'text': 'Да', 'color': 'positive'},
				{'text': 'Нет', 'color': 'negative'}
			],
			'commands': ['да', 'нет']
		}, {
			'id': 'nickname',
			'keyboard': [{'text': 'Назад', 'color': 'primary'}],
			'commands': ['назад']
		}, {
			'id': 'player',
			'keyboard': [{'text': 'Назад', 'color': 'primary'}],
			'commands': ['назад'],
			'level': 3
		}), GUI()
	def assoc(self, value):
		index = 'city'
		if value & assoc['fight']: return 'fight'
		else:
			if value & (assoc['forest'] | assoc['desert'] | assoc['swamp'] | assoc['opendoor'] | assoc['holiday'] | assoc['cave']):
				if value & assoc['forest']: index = 'forest'
				if value & assoc['desert']: index = 'desert'
				if value & assoc['swamp']: index = 'swamp'
				if value & assoc['opendoor']: index = 'opendoor'
				if value & assoc['holiday']: index = 'holiday'
				if value & assoc['cave']: index = 'cave'
			else:
				if (value & assoc['character']) and not (value & (assoc['inventory'] | assoc['craft'])): index = 'character'
				if value & assoc['inventory']: index = 'inventory'
				if value & assoc['craft']: index = 'craft'
				if value == assoc['tavern']: index = 'tavern'
				if value == assoc['map']: index = 'map'
				if value == assoc['traid']: index = 'traid'
				if value & assoc['dialog']: index = 'dialog'
				if value & assoc['nickname']: index = 'nickname'
				if value == assoc['player']: index = 'player'
		return index
	def tax(self, coins):
		self.world.save("UPDATE `world` SET `coins`=%r"%(int(self.world.one("SELECT `coins` FROM `world`")[0]) + math.floor(coins)))
		return math.floor(coins)
	def player(self, arr):
		if arr is not None:
			return {
				'id': arr[0],
				'xp': int(arr[5]),
				'level': int(arr[2]),
				'coins': int(arr[1]),
				'hp': arr[7],
				'is_travel': arr[8],
				'energy': arr[4],
				'inv': json.loads(arr[3]),
				'location': arr[9],
				'enemy': json.loads(arr[10]),
				'is_price': arr[6],
				'messages': int(arr[11]),
				'rating': arr[13],
				'vk_name': arr[12],
				'is_arena': json.loads(arr[14]),
				'upgrade': json.loads(arr[15]),
				'armor': json.loads(arr[16])
			}
		return None
	def read(self, file): # чтение из файла:
		f = open(file, 'r')
		text = f.read()
		f.close()
		return text
	def find(self, name=None, folder=None): # вывод найденных файлов:
		if name is not None:
			if folder is not '': folder += '/'
			arr = glob.glob(r'./dialog/' + folder + name + '*.txt')
			if len(arr): return arr
			else: return glob.glob(r'./dialog/' + folder + 'default_*.txt')
		return []
	def send(self, user_id=0, message='', keyboard=None): # отправка сообщений:
		try:
			arr = {'user_id': user_id, 'message': message, 'random_id': get_random_id() }
			if keyboard is not None: arr['keyboard'] = keyboard
			self.vk.method('messages.send', arr)
		except Exception as err:
			arr = {'user_id': user_id, 'message': message, 'random_id': get_random_id() }
			self.vk.method('messages.send', arr)
			self.gui.add_error(text='{0}: {1}'.format(user_id, err))
	def send_all(self, message=None, user_id=0): # отправка сообщения большому кол-ву человек:
		ids = []
		for user in self.query.many("SELECT * FROM `tavern`"):
			if not (user[0] == str(user_id)): ids.append(user[0])
		if len(ids): self.vk.method('messages.send', {'user_ids': ','.join(ids), 'message': message})
		self.gui.add_print(text="%s: %s"%(user_id, message), name=str(user_id))
	def time(self, value, is_time=True): # время:
		result, text = value - time.time() * is_time, "";
		if math.floor(result / 3600) > 0: text += "%r ч. "%math.floor(result / 3600)
		if math.floor(math.floor(result / 60) - math.floor(result / 3600) * 60) > 0: text += "%r мин. "%math.floor(math.floor(result / 60) - math.floor(result / 3600) * 60)
		if math.floor(result - math.floor(result / 60) * 60) > 0: text += "%r сек."%math.floor(result - math.floor(result / 60) * 60)
		return text
	def table(self, count=3): # редактировании описания группы:
		text, arr = "Копилка: %s\n\n&#128302; Лидеры арены:\n"%self.translate.number(int(self.world.one("SELECT `coins` FROM `world`")[0])), []
		for row in self.query.many("SELECT * FROM `users` WHERE `rating`>0"):
			user = self.player(row)
			arr.append({
				'vk_name': user['vk_name'],
				'rating': user['rating'],
				'level': user['level'],
				'id': user['id']
			})
		arr.sort(key=lambda i: i['rating'], reverse=True)
		for i in range(0, min(count, len(arr))): text += "%r. %s %s: %s\n"%(i + 1, arr[i]['vk_name'], icons['rating'], self.translate.number(arr[i]['rating']))
		self.session.groups.edit(group_id=self.group_id, description=text)
		return arr[:count]
	def replace(self, value):
		key = {}
		if value is not None:
			for i in value.split(', '):
				val = i.split(':')
				key[val[0]] = int(val[1].replace(' ', ''))
		else: return None
		return key
	def quest(self, arr):
		return {
			'name': arr[1],
			'need': self.replace(arr[2]),
			'users': self.replace(arr[3]),
			'price': self.replace(arr[4])
		}
	def item(self, name):
		arr, find = self.world.one("SELECT * FROM `items` WHERE `name`='%s'"%name), 0
		if arr is not None:
			if arr[2] is not None: find = assoc[arr[2]]
			return {
				'name': arr[0],
				'icon': arr[1],
				'location': find,
				'change': arr[3],
				'need': self.replace(arr[4]),
				'type': arr[5],
				'effect': arr[6]
			}
		return None
	def enemy(self, arr):
		find = 0
		if arr[2] is not None: find = assoc[arr[2]]
		return {
			'name': arr[0],
			'icon': arr[1],
			'location': find,
			'change': arr[3],
			'level': arr[7],
			'damage_change': arr[4],
			'leave_change': arr[5],
			'price': self.replace(arr[6]),
		}
	def travel(self, ID):
		arr = self.world.one("SELECT * FROM `location` WHERE `id`='%s'"%ID)
		if arr is not None:
			return {
				'name': arr[1],
				'icon': arr[2],
				'level': arr[4],
				'energy': arr[5],
				'price': self.replace(arr[6]),
				'need': self.replace(arr[8]),
				'time': arr[9]
			}
		return None
	def change_quests(self, count=3):
		self.world.save("UPDATE `quests` SET `active`=0,`users`=NULL")
		_max = self.world.one("SELECT COUNT(*) FROM `quests`")[0]
		while count:
			index = random.randint(0, _max - 1)
			if not self.world.one("SELECT * FROM `quests` LIMIT 1 OFFSET %r"%index)[0]:
				self.world.save("UPDATE `quests` SET `active`=1 LIMIT 1 OFFSET %r"%index)
				count -= 1
	def stats(self, data=None):
		armor, damage = 0, 0
		if data is not None:
			for row in ['head', 'body', 'weapon']:
				if row in data:
					item = self.item(data[row])
					if item is not None: 
						if row != 'weapon': armor += item['effect']
						else: damage += item['effect']
		return armor, damage
	def add_inv(self, inv=None, item=None, count=1):
		if item in inv: inv[item] += count
		else: inv[item] = count
		return inv
	def craft(self, inv=None, item=None):
		for row in item['need']:
			if row in inv:
				if inv[row] >= item['need'][row]: inv[row] -= item['need'][row]
				else: return None
			else: return None
		inv = self.add_inv(inv=inv, item=item['name'])
		return inv

class Local: # доп.функции:
	def __init__(self, core=None): self.core = core
	def dialog(self, numb=0, nickname=0, user_id=0):
		if not nickname:
			if numb > 0 and numb <= int(self.core.query.one("SELECT COUNT(*) FROM `traid`")[0]):
				slot = self.core.query.one("SELECT * FROM `traid` LIMIT 1 OFFSET %r"%(numb - 1))
				item = json.loads(slot[2])
				if slot[0] == str(user_id): text = "Вернуть слот с %r %s %s?"
				else: text = "Купить слот с %r %s %s " + "за %s %s?"%(self.core.translate.number(slot[3]), icons['coins'])
				return (text%(item['count'], self.core.item(item['name'])['icon'], item['name']) + "\n(да, нет)")
			else: text = "Этот слот уже куплен!"
		else: text = "Поменять имя? (100 %s)\n(да, нет)"%icons['coins']
		return text
	def traid(self, page=0, user_id=0, limit=5):
		_max, find = self.core.query.one("SELECT COUNT(*) FROM `traid`")[0], False
		text, count, offset, keys = "&#9878; Рынок: (страница %r из %r)\n"%(int(page / limit) + 1, math.ceil(_max / limit)), 0, page, []
		for row in self.core.query.many("SELECT * FROM `traid` LIMIT %r OFFSET %r"%(limit, page)):
			slot, offset, find = json.loads(row[2]), offset + 1, True
			item = self.core.item(slot['name'])
			if item is not None: text += "%r. продается %r шт. %s %s за %s %s\n"%(offset, slot['count'], item['icon'], item['name'], self.core.translate.number(row[3]), icons['coins'])
		if not find: text += "Ничего нет!\n"
		if page: keys.append({'text': 'Страница %r'%int(page / limit), 'color': 'positive'})
		if page < _max - limit: keys.append({'text': 'Страница %r'%int(page / limit + 2), 'color': 'positive'})
		if len(keys): keys.append({'line': 1})
		keys.append({'text': 'Персонаж', 'color': 'default'})
		keys.append({'line': 1})
		keys.append({'text': 'Назад', 'color': 'primary'})
		self.core.location._list['traid']['keyboard'] = keys
		return (text + "\n(купить <номер>, страница <номер>, назад)")
	def craft(self, page=0, inv=None): # мастерская:
		_max = self.core.world.one("SELECT COUNT(*) FROM `items` WHERE `need` IS NOT NULL")[0]
		text, keys = "&#9874; Мастерская: (страница %r из %r)\n"%(int(page / 5) + 1, math.ceil(_max / 5)), []
		for row in self.core.world.many("SELECT * FROM `items` WHERE `need` IS NOT NULL LIMIT 5 OFFSET %r"%page):
			item = self.core.item(row[0])
			if item is not None:
				text += "\n%s %s - нужно:\n"%(item['icon'], item['name'])
				for need in item['need']:
					c_item, count = self.core.item(need), 0
					if need in inv: count = inv[need]['count']
					if c_item is not None: text += "%s %s (%r из %r)\n"%(c_item['icon'], c_item['name'], count, item['need'][need])
		if page: keys.append({'text': 'Страница %r'%int(page / 5), 'color': 'positive'})
		if page < (_max - 5): keys.append({'text': 'Страница %r'%(int(page / 5) + 2), 'color': 'positive'})
		if len(keys): keys.append({'line': 1})
		keys.append({'text': 'Назад', 'color': 'primary'})
		self.core.location._list['craft']['keyboard'] = keys
		return (text + "\n(создать <предмет>, страница <номер>, назад)")
	def fight(self, data):
		if not (data['location'] & (assoc['attack'] | assoc['shield'])):
			if not ('type' in data['enemy']):
				enemy, commands, c_armor = self.core.enemy(self.core.world.one("SELECT * FROM `enemy` WHERE `name`='%s'"%data['enemy']['name'])), ['атака', 'защита'], (self.core.stats(data=data['armor']))
				text = "На вас напал %s %s!\n\nШанс &#9876; атаки: %r\nШанс &#128737; защиты: %r\n\n(атака, защита)"%(enemy['icon'], enemy['name'], enemy['damage_change'] + c_armor[1], enemy['leave_change'] + c_armor[0])
			else:
				arena_user = self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%data['is_arena']['username']))
				if arena_user is not None:
					if 'check' in arena_user['enemy']:
						text = "Ваше здоровье: %r/5 %s\nЗдоровье %s: %r/5 %s\n\nУ вас есть %s: 3 мин.\nВыберите действие: (aтака, защита)"%(data['hp'], icons['health'], arena_user['vk_name'], arena_user['hp'], icons['health'], icons['time'])
						commands = ['атака', 'защита', 'голова', 'тело', 'ноги']
					else: text, commands = "Ожидайте ответа от второго игрока!", []
			keyboard = [
				{'text': 'Атака', 'color': 'positive'},
				{'text': 'Защита', 'color': 'default'}
			]
		else:
			text = "Выберите часть тела, которую нужно %s\n(голова, тело, ноги)"%['защитить', 'атаковать'][bool(data['location'] & assoc['attack'])]
			keyboard, commands = [
				{'text': 'Голова', 'color': 'positive'}, {'line': 1},
				{'text': 'Тело', 'color': 'positive'}, {'line': 1},
				{'text': 'Ноги', 'color': 'positive'}, {'line': 1},
				{'text': 'Назад', 'color': 'primary'}
			], ['голова', 'тело', 'ноги', 'назад']
		return text, keyboard, commands

class Game: # игра:
	def __init__(self, core): 
		self.core = core
		self.local = Local(core=self.core)
	def add_user(self, user_id): # новый игрок:
		text, is_price = self.core.read('./dialog/start.txt'), int(self.core.check.member(user_id));
		if is_price: text += "\n\nБольшое спасибо за подписку!\nВаш %s бонус: +20 %s!"%(icons['price'], icons['coins']);
		data = self.core.session.users.get(user_ids=user_id)[0];
		self.core.query.save("INSERT INTO `users` (username, coins, level, xp, energy, is_price, hp, is_travel, location, inv, enemy, messages, vk_name, is_arena, upgrade, armor) VALUES (%s, %r, %r, %r, %r, %r, %r, %r, 0, '{}', '{}', 0, '%s', '{}', '[]', '{}')"%(str(user_id), is_price * 20, 1, 0, 5, is_price, 5, 0, data['first_name'] + ' ' + data['last_name']));
		self.core.gui.add_print(text="новый пользователь: %s!"%(data['first_name'] + ' ' + data['last_name']), name=data['first_name'] + ' ' + data['last_name'])
		return text;
	def clear(self): # применение запросов:
		if len(commands):
			self.core.query.save(';'.join(commands) + ';');
			commands.clear();
	def level(self, level): return level * 5 + (level + 1)**2; # нужное кол-во опыта для уровня.
	def change(self, value): return (value / 100) >= random.random(); # drop change.
	def finish(self, data=None, user_id=0): # конец похода:
		if data is not None:
			if data['is_travel'] - time.time() < 0 and data['is_travel']:
				val = self.core.assoc(data['location'])
				if val in Travel:
					text, arr, travel = "Сводка (%s %s): \n\n"%(Travel[val]['icon'], Travel[val]['name']), [], find_story(travel_finish)
					obj = self.quest(value=val, data=data, user_id=user_id)
					data = obj[0]
					for row in obj[1]: text += row + '\n\n'
					for row in Travel[val]['price']: # награда:
						value = Travel[val]['price'][row]
						if travel[1] is not None:
							if row in travel[1]: value += travel[1][row]
						if travel[2] is not None:
							if row in travel[2]: value -= travel[2][row]
						if row == 'coins': self.core.tax(abs(math.ceil(value * .25)))
						data[row] += value
						arr.append("%r %s"%(value, icons[row]))
					for row in self.core.world.many("SELECT `name` FROM `items` WHERE `location`='%s'"%val):
						item = self.core.item(row[0])
						if item is not None:
							if self.change(item['change']):
								obj = self.quest(value=item['name'], data=data, user_id=user_id)
								data = obj[0]
								data['inv'] = self.core.add_inv(inv=data['inv'], item=item['name'])
								for key in obj[1]: text += key + '\n\n'
								arr.append("%s %s"%(item['icon'], item['name']))
					data, levelup = self.up(data=data)
					if levelup is not None: text += levelup + '\n\n'
					text += "%s\n\nДобыча: %s"%(travel[0], ', '.join(arr))
					key = VkKeyboard(one_time=True)
					key.add_button('Назад', color='primary')
					self.core.gui.add_print(text="%s пришел из %s!"%(data['vk_name'], Travel[val]['name']), name=data['vk_name'])
					commands.append("UPDATE `users` SET `inv`='%s',`is_travel`=0,`enemy`='{}',`messages`=0,`coins`=%r,`xp`=%r,`level`=%r,`energy`=%r,`hp`=%r,`location`=0 WHERE `username`=%s"%(json.dumps(data['inv']), data['coins'], data['xp'], data['level'], data['energy'], data['hp'], user_id))
					self.clear()
					return [text + "\n(назад)", key]
		return None
	def quest(self, user_id=0, value=None, data=None, save=False): # выполнение квеста:
		arr = []
		if value != 'all':
			def replace(ndata):
				ntext = ""
				for key in ndata: ntext += "%s: %r, "%(key, ndata[key])
				return ntext[:len(ntext) - 2]
			for row in self.core.world.many("SELECT * FROM `quests` WHERE `active`=1"):
				quest, find = self.core.quest(row), True
				if quest['need'] is not None:
					for key in quest['need']:
						if value == key:
							if quest['users'] is not None:
								if str(user_id) in quest['users']: 
									if quest['users'][str(user_id)] < quest['need'][key]:
										quest['users'][str(user_id)] += 1
										find = False
								else: quest['users'][str(user_id)], find = 1, False
							else: 
								quest['users'], find = {}, False
								quest['users'][str(user_id)] = 1
							self.core.world.save("UPDATE `quests` SET `users`='%s' WHERE `name`='%s'"%(replace(quest['users']), quest['name']))
					if not find:
						if quest['users'] is not None:
							if str(user_id) in quest['users']:
								if quest['users'][str(user_id)] >= quest['need'][key]:
									text = ''
									for items in quest['price']:
										if items in ['xp', 'coins']:
											data[items] += quest['price'][items]
											text += "+%r %s "%(quest['price'][items], icons[items])
										else:
											item = self.core.item(items)
											if item is not None:
												data['inv'] = self.core.add_inv(inv=data['inv'], item=item['name'], count=quest['price'][items])
												text += "%r шт. %s %s "%(quest['price'][items], item['icon'], item['name'])
									arr.append("Квест <%s> выполнен!\nНаграда: %s"%(quest['name'], text))
									# выполнение всех квестов:
									count = 0
									for c_row in self.core.world.many("SELECT * FROM `quests` WHERE `active`=1"):
										c_quest = self.core.quest(c_row)
										if c_quest['users'] is not None:
											if str(user_id) in c_quest['users']:
												for c_key in c_quest['need']:
													if c_quest['users'][str(user_id)] >= c_quest['need'][c_key]: count += 1
									if count == 3: self.quest(user_id=user_id, value='all', data=data, save=True)
									break
			
		else:
			item = self.core.item('ключ')
			if item is not None:
				data['coins'] += 40
				data['xp'] += 20
				data['inv'] = self.core.add_inv(inv=data['inv'], item=item['name'])
				arr.append("&#10024; Вы выполнили все ежедневные квесты!\nНаграда: +20 %s, +40 %s, 1шт. %s %s"%(icons['xp'], icons['coins'], item['icon'], item['name']))
		if not save: return [data, arr]
		else:
			self.core.query.save("UPDATE `users` SET `inv`='%s',`xp`=%r,`coins`=%r WHERE `username`=%s"%(json.dumps(data['inv']), data['xp'], data['coins'], str(user_id)))
			if len(arr): self.core.send(user_id=user_id, message='\n\n'.join(arr))
	def up(self, data=None): # level up:
		text = None
		if data is not None:
			if data['xp'] >= self.level(data['level']) and data['level'] < 20:
				data['coins'] += 20
				data['level'] += 1
				data['xp'], data['hp'], data['energy'], arr = data['xp'] - self.level(data['level'] - 1), 5, 5 * (2 - int(not 'энергохранилище' in data['upgrade'])), []
				if data['level'] < 20: text = "&#10024;&#10024;&#10024; Вы получили %r уровень! &#10024;&#10024;&#10024;\n+20&#128176; %r/%r%s\n\n"%(data['level'], data['energy'], 5 * (2 - int(not 'энергохранилище' in data['upgrade'])), icons['energy']);
				else:
					text = self.core.read('dialog/finish.txt') + "\n\n"
					self.core.session.wall.post(owner_id=-self.core.group_id, from_group=1, message="&#10024; Поздравляю! %s достиг максимального уровня в игре!"%data['vk_name'])
				for row in self.core.world.many("SELECT * FROM `enemy` WHERE `level`=%r"%data['level']):
					enemy = self.core.enemy(row)
					if enemy is not None: arr.append("%s %s"%(enemy['icon'], enemy['name']))
				for row in Travel:
					if data['level'] == Travel[row]['level']: arr.append("%s %s"%(Travel[row]['icon'], Travel[row]['name']))
				if len(arr): text += "Вам открылись: %s"%(', '.join(arr))
				self.core.gui.add_print(text="%s получил %r уровень!"%(data['vk_name'], data['level'] + 1), name=data['vk_name'])
		return [data, text];
	def update(self, command=None, user_id=0): # переходы по локациям:
		text, keyboard, data = "", VkKeyboard(one_time=True), self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%user_id))
		is_keyboard, is_message, is_update, is_reload = 1, 1, 1, False
		if data is not None:
			local = self.core.assoc(data['location'])
			if local == 'fight':
				val = self.local.fight(data)
				self.core.location._list[local]['commands'] = val[2]
			if local in self.core.location._list: global_find = re.findall('^(%s|%s)'%('|'.join(self.core.location._list[local]['commands']), '|'.join(admin)), command, re.IGNORECASE)
			else: global_find, is_keyboard = None, 0 
			if global_find:
				find, arr = global_find[0].lower(), {
					'персонаж': 'character',
					'инвентарь': 'inventory',
					'мастерская': 'craft',
					'карта': 'map',
					'рынок': 'traid',
					'таверна': 'tavern',
					'лес': 'forest',
					'болото': 'swamp',
					'пустыня': 'desert',
					'новогодняя пещера': 'holiday',
					'сменить имя': 'dialog',
					'пещера': 'cave',
					'арена': 'player'
				}
				try:
					if find == 'назад':
						if data['location'] & assoc['player']:
							if not (data['location'] & assoc['fight']): # выход из арены:
								commands.append("DELETE FROM `arena` WHERE `username`=%s"%user_id)
								data['location'] &=~ assoc[local]
							else:
								if not data['enemy']['check']:
									if data['location'] & assoc['attack']: data['location'] &=~ assoc['attack']
									if data['location'] & assoc['shield']: data['location'] &=~ assoc['shield']
								else: text, is_keyboard, is_update = "Вы уже сделали ход!", 0, 0
						else:
							if data['location'] == assoc['tavern']: # выход из таверны:
								commands.append("DELETE FROM `tavern` WHERE `username`=%s"%user_id)
								self.core.send_all(user_id=user_id, message="%s вышел из таверны!"%data['vk_name'])
							data['location'] &=~ assoc[local]
					elif find == 'бармен':
						is_update, is_keyboard, narr = 0, 0, self.core.translate.barmen(command)
						if narr is not None:
							if narr['username'] != data['vk_name']:
								user = self.core.query.one("SELECT `username` FROM `users` WHERE `vk_name`='%s'"%narr['username'])
								if user is not None:
									if self.core.query.one("SELECT * FROM `tavern` WHERE `username`=%s"%user[0]) is not None:
										self.core.send(user_id=user[0], message="Новое сообщение от %s!\n%s"%(data['vk_name'], narr['message']))
									else: commands.append("INSERT INTO `mail` (user_id,message,from_id) VALUES (%s,'%s','%s')"%(user[0], narr['message'], data['vk_name']))
								else: raise Exception("Персонажа с таким именем не существует!")
								text = "Ваше сообщение было отправлено!"
							else: text = "Как я вам передам это сообщения, если получатель - это Вы?!"
						else: text = "Чтобы отправить сообщение другому игроку напишите:\nбармен передай <имя>: <сообщение>"
					elif find == 'таверна': # вход в таверну:
						if data['level'] >= self.core.location._list['tavern']['level']:
							if data['level'] >= 20: data['vk_name'] = "%s %s"%('&#11088;', data['vk_name'])
							self.core.send_all(user_id=user_id, message="%s зашел в таверну!"%data['vk_name'])
							commands.append("INSERT INTO `tavern` (username,vk_name) VALUES (%s, '%s')"%(user_id, data['vk_name']))
						else: raise Exception("Вам нужен %r уровень!"%self.core.location._list['tavern']['level'])
					elif (find == 'карта' or find == 'рынок') and not data['hp']: raise Exception("%s Вас выпищут через %s: %s"%(icons['health'], icons['time'], self.core.time(data['messages'])))
					elif find == 'арена': # арена:
						if data['level'] >= self.core.location._list['player']['level']:
							if data['hp'] >= 5:
								self.core.query.save("INSERT INTO `arena` (username,rating,level) VALUES (%s,%r,%r)"%(user_id, data['rating'], data['level']))
							else: raise Exception("Вы ранены и не можете принять участия на арене!")
						else: raise Exception("Требуется %r уровень!"%self.core.location._list['player']['level'])
					elif find in self.core.location._list['map']['commands']: # отправление в поход:
						if data['level'] >= Travel[arr[find]]['level']:
							if data['energy'] >= Travel[arr[find]]['energy']:
								add = ""
								if Travel[arr[find]]['need'] is not None:
									for item in Travel[arr[find]]['need']:
										if item in data['inv']:
											if data['inv'][item]['count'] >= Travel[arr[find]]['need'][item]:
												data['inv'][item]['count'] -= 1
												add += ",`inv`='%s'"%json.dumps(data['inv'])
										if add == "": raise Exception("Вам нужен %s %s!"%(item, self.core.item(item)['icon']))
								data['location'] |= assoc[arr[find]]
								commands.append("UPDATE `users` SET `is_travel`=%r,`energy`=%r,`location`=%r%s WHERE `username`=%s"%(time.time() + Travel[arr[find]]['time'] * (1 - .5 * int('лошадь' in data['upgrade'])), data['energy'] - Travel[arr[find]]['energy'], data['location'], add, user_id))
								is_update, is_keyboard, dialogs = 0, 0, self.core.find(name=find + '_', folder='start')
								if len(dialogs): text = self.core.read(dialogs[random.randint(0, len(dialogs) - 1)])
								else: text = "Вы отправились в %s %s!"
								text = text%(Travel[arr[find]]['icon'], Travel[arr[find]]['name']) + "\nВозвращение через %s: %s"%(icons['time'], self.core.time(time.time() + Travel[arr[find]]['time'] * (1 - .5 * int('лошадь' in data['upgrade']))))
							else: raise Exception("Недостаточно %s энергии!"%icons['energy'])
						else: raise Exception("Вам нужен %r уровень!"%Travel[arr[find]]['level'])
					elif find in ['атака', 'защита']: # сражения:
						if not ('type' in data['enemy']):
							is_update, is_keyboard, enemy = 0, 0, self.core.enemy(self.core.world.one("SELECT * FROM `enemy` WHERE `name`='%s'"%data['enemy']['name']))
							if enemy is not None:
								arr, c_armor = [], (self.core.stats(data=data['armor']))
								change, weapon = self.change((enemy['damage_change'] + c_armor[0]) * (find == 'атака') + (enemy['leave_change'] + c_armor[1]) * (find == 'защита')), None
								if change:
									if find == 'атака': self.quest(value=enemy['name'], data=data, user_id=user_id, save=True)
									for key in enemy['price']:
										if key in ['coins', 'xp']:
											data[key] += enemy['price'][key]
											arr.append("+%r %s"%(enemy['price'][key], icons[key]))
										else:
											if find == 'атака':
												item = self.core.item(key)
												if item is not None:
													data['inv'] = self.core.add_inv(inv=data['inv'], item=key, count=enemy['price'][key])
													self.quest(value=key, data=data, user_id=user_id, save=True)
													arr.append("%r шт. %s %s"%(enemy['price'][key], item['icon'], key))
								if 'weapon' in data['armor']: weapon = data['armor']['weapon'] + '_'
								dialogs = self.core.find(name=weapon, folder=['lose', 'win'][change])
								if len(dialogs): text = self.core.read(dialogs[random.randint(0, len(dialogs) - 1)])%(enemy['icon'], enemy['name'])
								else:
									if find == 'атака':
										if change: text = "Вы победили %s %s!"%(enemy['icon'], enemy['name'])
										else: text = "%s %s Набросился на вас!\n%r/5 %s"%(enemy['icon'], enemy['name'], data['hp'] - 1, icons['health'])
									else:
										if change: text = "Вы сбежали от %s %s!"%(enemy['icon'], enemy['name'])
										else: text = "Вы не смогли сбежать от %s %s!\n%r/5 %s"%(enemy['icon'], enemy['name'], data['hp'] - 1, icons['health'])
								if change: text += "\nНаграда: %s"%(', '.join(arr))
								else: data['hp'] -= 1
								if data['hp'] > 0:
									data['location'] &=~ assoc['fight']
									text += "\n\nОсталось %s: %s"%(icons['time'], self.core.time(time.time() + data['is_travel']))
									commands.append("UPDATE `users` SET `coins`=%r,`xp`=%r,`inv`='%s',`enemy`='{}',`location`=%r,`hp`=%r,`is_travel`=%r WHERE `username`=%s"%(data['coins'], data['xp'], json.dumps(data['inv']), data['location'], data['hp'], time.time() + data['is_travel'], user_id))
								else:
									data['location'] = 0
									commands.append("UPDATE `users` SET `location`=%r, `hp`=%r,`messages`=%r,`is_travel`=0,`enemy`='{}' WHERE `username`=%s"%(data['location'], data['hp'], time.time() + 3600, user_id))
									raise Exception("Вы были сильно ранены!\nВас отнесли обратно в лагерь.\n\n(назад)")
						else:
							if find == 'атака': data['location'] |= assoc['attack']
							if find == 'защита': data['location'] |= assoc['shield']
					elif find == 'да': # соглашение:
						data['location'] &=~ assoc['dialog'];
						if (data['location'] & assoc['traid']) and not (data['location'] & assoc['character']): # покупка/возврат предмета:
							slot = self.core.query.one("SELECT * FROM `traid` LIMIT 1 OFFSET %r"%(data['messages'] - 1))
							c_item = json.loads(slot[2])
							item = self.core.item(c_item['name'])
							if slot[0] != str(user_id):
								data['coins'] -= slot[3]
								self.core.tax(math.floor(slot[3] * .05))
								new_price = math.floor(slot[3] - slot[3] * .05)
								profile = self.core.query.one("SELECT `coins` FROM `users` WHERE `username`=%s"%slot[0])
								self.core.send(user_id=slot[0], message="%s купил у вас %r %s %s за %s %s!"%(data['vk_name'], c_item['count'], item['icon'], item['name'], self.core.translate.number(new_price), icons['coins']))
								commands.append("UPDATE `users` SET `coins`=%r WHERE `username`=%s"%(profile[0] + new_price, slot[0]))
							data['inv'] = self.core.add_inv(inv=data['inv'], item=c_item['name'], count=c_item['count'])
							commands.append("DELETE FROM `traid` LIMIT 1 OFFSET %r"%(data['messages'] - 1))
							commands.append("UPDATE `users` SET `inv`='%s',`coins`=%r WHERE `username`=%s"%(json.dumps(data['inv']), data['coins'], user_id))
							self.core.gui.add_print(text="%s купил %r шт. %s за %r"%(data['vk_name'], c_item['count'], item['name'], slot[3]), name=data['vk_name'])
							raise Exception("Вы %s %r шт. %s %s за %s %s!"%(['вернули', 'купили'][slot[0] != str(user_id)], c_item['count'], item['icon'], item['name'], self.core.translate.number(slot[3]), icons['coins']))
						else: # смена ника и сражения:
							if data['location'] & assoc['player']:
								data['location'] |= assoc['fight']
								data['enemy'], data['messages'] = {
									'type': 'player',
									'check': 0
								}, time.time() + 180
								arena_user = self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%data['is_arena']['username']))
								if arena_user is not None:
									commands.append("UPDATE `users` SET `enemy`='%s',`messages`=%r WHERE `username`=%s"%(json.dumps(data['enemy']), data['messages'], user_id))
									if 'check' in arena_user['enemy']:
										self.clear()
										val = self.local.fight(arena_user)
										self.core.location._list['fight']['keyboard'], self.core.location._list['fight']['commands'] = val[1], val[2]
										self.core.send(user_id=data['is_arena']['username'], message="Бой начался!\n%s"%val[0], keyboard=self.core.location.keyboard('fight').get_keyboard())
							else:
								if data['coins'] >= 100: data['location'] |= assoc['nickname']
								else: raise Exception("Вам требуется 100 %s!"%icons['coins'])
					elif find == 'нет': # отказ:
						data['location'] &=~ assoc['dialog'];
						if data['location'] & assoc['player']:
							text, is_update, is_keyboard = "Вы вернулись в очередь!", 0, 0
							self.core.send(user_id=data['is_arena']['username'], message="Игрок отказался сражаться!\nВы возвращаетесь в очередь!")
							commands.append("UPDATE `users` SET `is_arena`='{}',`location`=%r,`enemy`='{}' WHERE `username`=%s"%(data['location'], user_id))
							commands.append("UPDATE `users` SET `is_arena`='{}',`location`=%r,`enemy`='{}' WHERE `username`=%s"%(data['location'], data['is_arena']['username']))
							commands.append("INSERT INTO `arena` (username,rating,level) VALUES (%s,%r,%r)"%(data['is_arena']['username'], 0, 0))
							commands.append("INSERT INTO `arena` (username,rating,level) VALUES (%s,%r,%r)"%(user_id, 0, 0))
					elif find in ['купить', 'продать', 'использовать', 'создать', 'страница']:	
						obj = self.core.translate.text(command);
						if obj is not None:
							if find == 'купить': # покупка:
								if obj['count'] in range(1, self.core.query.one("SELECT COUNT(*) FROM `traid`")[0] + 1):
									slot = self.core.query.one("SELECT * FROM `traid` LIMIT 1 OFFSET %r"%(obj['count'] - 1))
									if slot is not None:
										if (data['coins'] >= slot[3]) or (str(user_id) == slot[0]):
											data['location'] |= assoc['dialog']
											data['messages'] = obj['count']
											commands.append("UPDATE `users` SET `messages`=%r WHERE `username`=%s"%(data['messages'], user_id))
										else: raise Exception("У вас недостаточно монет %s!"%icons['coins'])
									else: raise Exception("Такого слота не существует!")
								else: raise Exception("Такого слота не существует!")
							else:
								item = self.core.item(obj['item'])
								if item is not None:	
									if find == 'создать': # создание предмета:
										if 'need' in item:
											inv = self.core.craft(inv=data['inv'], item=item)
											if inv is not None:
												commands.append("UPDATE `users` SET `inv`='%s' WHERE `username`=%s"%(json.dumps(inv), user_id))
												self.quest(value=item['name'], data=data, user_id=user_id, save=True)
												raise Exception("Вы создали %s %s!"%(item['icon'], item['name']))
											else: raise Exception("Недостаточно ресурсов!")
										else: raise Exception("Этот предмет невозможно создать!")
									elif find == 'продать': # продажа предметов:
										if item['name'] in data['inv']:
											if data['inv'][item['name']] >= obj['count']:
												data['inv'][item['name']] -= obj['count']
												commands.append("UPDATE `users` SET `inv`='%s' WHERE `username`=%s"%(json.dumps(data['inv']), user_id))
												commands.append("INSERT INTO `traid` (username, vk_name, item, buy) VALUES (%s, '%s', '%s', %r)"%(user_id, data['vk_name'], json.dumps({'name': item['name'], 'count': obj['count']}), obj['price']))
												self.quest(value='sell', data=data, user_id=user_id, save=True)
												self.core.gui.add_print(text="%s продал %r шт. %s за %r"%(data['vk_name'], obj['count'], item['name'], obj['price']), name=data['vk_name'])
												raise Exception("Вы продали %r шт. %s %s за %r %s!"%(obj['count'], item['icon'], item['name'], obj['price'], icons['coins']))
											else: raise Exception("Недостаточно ресурсов!")
										else: raise Exception("У вас нет %s %s!"%(item['icon'], item['name']))
									elif find == 'использовать': # использование предмета:
										if item['name'] in data['inv']:
											if data['inv'][item['name']] > 0:
												if 'type' in item:
													data['inv'][item['name']] -= 1
													if item['type'] == 'upgrade': # улучшения:
														if item['name'] in data['upgrade']: raise Exception("У вас уже установлен %s %s!"%(item['icon'], item['name']))
														data['upgrade'].append(item['name'])
														commands.append("UPDATE `users` SET `upgrade`='%s',`inv`='%s' WHERE `username`=%s"%(json.dumps(data['upgrade']), json.dumps(data['inv']), user_id))
														raise Exception("%s %s установлен!"%(item['icon'], item['name']))
													elif item['type'] == 'lootbox': # коробки:
														arr = []
														for row in item['need']:
															if row != 'coins':
																c_item = self.core.item(row)
																if c_item is not None: 
																	data['inv'] = self.core.add_inv(inv=data['inv'], item=c_item['name'], count=item['need'][row])
																	arr.append("%r шт. %s %s"%(item['need'][row], c_item['icon'], c_item['name']))
															else:
																data[row] += item['need'][row]
																arr.append("+%r %s"%(item['need'][row], icons['coins']))
														commands.append("UPDATE `users` SET `inv`='%s',`coins`=%r WHERE `username`=%s"%(json.dumps(data['inv']), data['coins'], user_id))
														raise Exception("Вы открыли %s %s!\nНаграда: %s"%(item['icon'], item['name'], ', '.join(arr)))
													elif item['type'] in ['weapon', 'head', 'body']: # экипировка:
														if item['type'] in data['armor']: data['inv'] = self.core.add_inv(inv=data['inv'], item=data['armor'][item['type']])
														data['armor'][item['type']] = item['name']
														commands.append("UPDATE `users` SET `inv`='%s',`armor`='%s' WHERE `username`=%s"%(json.dumps(data['inv']), json.dumps(data['armor']), user_id))
														raise Exception("Вы взяли %s %s!"%(item['icon'], item['name']))
													elif item['type'] == 'health': # зелья:
														data['hp'] = min(data['hp'] + item['effect'], 5)
														commands.append("UPDATE `users` SET `inv`='{0}',`hp`={1} WHERE `username`={2}".format(json.dumps(data['inv']), data['hp'], user_id))
														raise Exception("Вы использовали %s %s!\n+%r %s здоровье! %r/5 %s"%(item['icon'], item['name'], item['effect'], icons['health'], data['hp'], icons['health']))
												else: raise Exception("Этот предмет нельзя использовать!")
											else: raise Exception("Недостаточно ресурсов!")
										else: raise Exception("У вас нет %s %s!"%(item['icon'], item['name']))	
								else:
									if find == 'страница': # переход по страницам:
										page, is_update = max(obj['count'] - 1, 0), 0
										if data['location'] == assoc['traid']:
											if page < math.ceil(self.core.query.one("SELECT COUNT(*) FROM `traid`")[0] / 5): text, keyboard = self.local.traid(page=page * 5, user_id=user_id), self.core.location.keyboard('traid')
											else: raise Exception("Страница не существует!")
										elif data['location'] & assoc['craft']: text, keyboard = self.local.craft(page=page * 5, inv=data['inv']), self.core.location.keyboard('craft')
									else: raise Exception("Предмета %s не существует!"%obj['item'])
					elif find in admin:
						obj = self.core.translate.text(command)
						if obj is not None:
							if self.core.check.admin(user_id):
								if find == '!забанить': # user blocked:
									user = self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `vk_name`='%s'"%obj['item']))
									if user is not None:
										text, is_update, is_keyboard = "Игрок %s заблокирован!\nПричина:%s"%(obj['item'], obj['price']), 0, 0
										self.core.send(user_id=user['id'], message="Вы были заблокированы!\nПричина: %s"%obj['price'])
										self.core.query.save("UPDATE `users` SET `hp`=5,`location`=0,`energy`=5,`enemy`='{}',`is_travel`=0,`messages`=0 WHERE `vk_name`='%s'"%user['id'])
										if self.core.query.one("SELECT * FROM `tavern` WHERE `username`=%s"%user['id']):
											self.core.query.save("DELETE FROM `tavern` WHERE `username`=%s"%user['id'])
											self.core.send_all(message="%s был выгнан из таверны!"%obj['item'], user_id=user_id)
										self.core.session.groups.ban(group_id=self.core.group_id, owner_id=user['id'], comment=obj['price'])
									else: raise Exception("Игрока %s не существует!"%obj['item'])
								elif find == '!отправить': # отправка предметов игрокам:
									user = self.core.query.one("SELECT `inv`,`username` FROM `users` WHERE `vk_name`='%s'"%obj['price'])
									if user is not None:
										inv, item = json.loads(user[0]), self.core.item(obj['item'])
										if item is not None:
											if item['name'] in inv: inv[item['name']]['count'] += obj['count']
											else: inv[item['name']] = {'name': item['name'], 'count': obj['count']}
											self.core.send(user_id=user[1], message="&#128230; Посылка: %r шт %s %s!"%(obj['count'], item['icon'], item['name']))
											commands.append("UPDATE `users` SET `inv`='%s' WHERE `username`=%s"%(json.dumps(inv), user[1]))
											raise Exception("Вы отправили игроку %s: %r %s %s!"%(obj['price'], obj['count'], item['icon'], item['name']))
										else: raise Exception("Предмета %s не существует!"%obj['item'])
									else: raise Exception("Игрока %s не существует!"%obj['price'])
						elif find == '!инфо': text, is_keyboard, is_update = "Версия: 1.0\nАвтор: @mgcat(Magic Cat)", 0, 0
					elif find in ['голова', 'тело', 'ноги']: # pvp:
						is_update, is_keyboard = 0, 0
						if not data['enemy']['check']:
							attack_assoc, arena_user = {1: 'голова', 2: 'тело', 3: 'ноги'}, self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%data['is_arena']['username']))
							if arena_user is not None:
								if data['location'] & assoc['attack']: data['enemy']['check'] = assoc['attack']
								if data['location'] & assoc['shield']: data['enemy']['check'] = assoc['shield']
								data['location'] &=~ data['enemy']['check']
								data['enemy']['check'] += (find == 'голова') + 2 * (find == 'тело') + 3 * (find == 'ноги')
								commands.append("UPDATE `users` SET `enemy`='%s',`messages`=%r WHERE `username`=%s"%(json.dumps(data['enemy']), time.time() + 180, user_id))
								if arena_user['enemy']['check']: # просчет хода:
									value, arena_value, arena_text = data['enemy']['check'], arena_user['enemy']['check'], ''
									if value & assoc['attack']:
										value -= assoc['attack']
										if arena_value & assoc['attack']:
											arena_value -= assoc['attack']
											if value != arena_value:
												c_text = "%s ударил по %s! -2 %s"
												text, arena_text = c_text%(arena_user['vk_name'], attack_assoc[arena_value], icons['health']), c_text%(data['vk_name'], attack_assoc[value], icons['health'])
												data['hp'] -= 2
												arena_user['hp'] -= 2
											else:
												c_text = "Вы смягчили удар по себе! -1 %s"%icons['health']
												text, arena_text = c_text, c_text 
												data['hp'] -= 1
												arena_user['hp'] -= 1
										else:
											arena_value -= assoc['shield']
											if value != arena_value:
												text, arena_text = "Вы нанесли удар!", "%s ударил по %s! -1 %s"%(data['vk_name'], attack_assoc[value], icons['health'])
												arena_user['hp'] -= 2
											else: text, arena_text = "Вы не смогли пробить щит!", "Вы защитились от удара!"
									else:
										if arena_value & assoc['attack']:
											value -= assoc['shield']
											arena_value -= assoc['attack']
											if arena_value != value:
												text = "%s ударил по %s! -2 %s"%(arena_user['vk_name'], attack_assoc[arena_value], icons['health'])
												arena_text = "Вы нанесли удар!"
												data['hp'] -= 2
											else: text, arena_text = "Вы защитились от удара!", "Вы не смогли пробить щит!"
										else:
											text = "Вы стоите перед друг-другом и не можете понять что происходит?"
											arena_text = text
									if data['location'] & assoc['attack']: data['location'] &=~ assoc['attack']
									if data['location'] & assoc['shield']: data['location'] &=~ assoc['shield']
									if data['hp'] <= 0 or arena_user['hp'] <= 0: # итог сражения:
										self.quest(value='arena', data=data, user_id=user_id, save=True)
										self.quest(value='arena', data=arena_user, user_id=data['is_arena']['username'], save=True)
										if data['hp'] <= 0 and arena_user['hp'] <= 0:
											text = "Ничья! +1 %s, +5 %s\n(назад)"%(icons['rating'], icons['coins'])
											arena_text = text
											data['rating'] += 1
											data['coins'] += 5
											arena_user['rating'] += 1
											arena_user['coins'] += 5
											self.core.tax(10)
										else:
											text = "Вы проиграли: -2 %s!"%icons['rating']
											arena_text = "Победа: +2 %s!\nНаграда: +10 %s"%(icons['rating'], icons['coins'])
											if data['hp'] <= 0: # проигрышь:
												data['rating'] = max(data['rating'] - 2, 0)
												arena_user['rating'] += 2
												arena_user['coins'] += 10
											else: # победа:
												arena_user['rating'] = max(arena_user['rating'] - 2, 0)
												data['rating'] += 2
												data['coins'] + 10
												text, arena_text = arena_text, text
											self.core.tax(10)
											text += "\n(назад)"
										is_keyboard, data['location'] = 1, 0
										keyboard.add_button('Назад', color='primary')
										commands.append("UPDATE `users` SET `hp`=5,`location`=0,`enemy`='{}',`is_arena`='{}',`messages`=0,`rating`=%r,`coins`=%r WHERE `username`=%s"%(data['rating'], data['coins'], user_id))
										commands.append("UPDATE `users` SET `hp`=5,`location`=0,`enemy`='{}',`is_arena`='{}',`messages`=0,`rating`=%r,`coins`=%r WHERE `username`=%s"%(arena_user['rating'], arena_user['coins'], data['is_arena']['username']))
										self.clear()
										self.core.send(user_id=data['is_arena']['username'], message=arena_text + "\n(назад)", keyboard=keyboard.get_keyboard())
									else:
										data['enemy']['check'], arena_user['enemy']['check'] = 0, 0
										commands.append("UPDATE `users` SET `hp`=%r,`enemy`='%s',`location`=%r WHERE `username`=%s"%(data['hp'], json.dumps(data['enemy']), data['location'], user_id))
										commands.append("UPDATE `users` SET `hp`=%r,`enemy`='%s',`location`=%r WHERE `username`=%s"%(arena_user['hp'], json.dumps(arena_user['enemy']), data['location'], data['is_arena']['username']))
										self.clear()
										is_keyboard, val, val2 = 1, self.local.fight(data), self.local.fight(arena_user)
										self.core.location._list['fight']['keyboard'] = val[1]
										self.core.location._list['fight']['commands'] = val[2]
										keyboard, text = self.core.location.keyboard('fight'), text + "\n\n" + val[0]
										self.core.send(user_id=data['is_arena']['username'], message="%s\n\n%s"%(arena_text, val2[0]), keyboard=keyboard.get_keyboard())
								else: text = "Ожидайте хода %s!"%arena_user['vk_name']
						else: text = "Вы уже сделали ход!"
					if find in arr: data['location'] |= assoc[arr[find]]
				except Exception as msg:
					text, is_update, local = msg.args[0], 0, self.core.assoc(data['location'])
					if local in self.core.location._list: keyboard = self.core.location.keyboard(local)
					else: is_keyboard = 0
			else:
				if local in self.core.location._list: keyboard = self.core.location.keyboard(local)
				else: is_keyboard = 0
				if local == 'tavern': # отправка сообщений в таверну:
					is_message, is_update = 0, 0
					if data['level'] >= 20: data['vk_name'] = "%s %s"%('&#11088;', data['vk_name'])
					self.core.send_all(user_id=user_id, message=self.core.translate.rp(message=command, name=data['vk_name']))
					self.core.vk.method('messages.markAsRead', {'peer_id': user_id});
				elif local == 'nickname': # смена имени:
					is_update = 0
					if self.core.query.one("SELECT * FROM `users` WHERE `vk_name`='%s'"%command) is None:
						if re.match(r'[^\d+]\D+(\d+)?', command):
							if len(command) <= 15:
								self.core.gui.add_print(text="%s сменил имя на: %s"%(data['vk_name'], command), name=data['vk_name'])
								commands.append("UPDATE `users` SET `vk_name`='%s',`coins`=%r WHERE `username`=%s"%(command, data['coins'] - 100, user_id))
								data['location'] &=~ assoc['nickname']
								self.core.tax(100)
								text = "&#128221; Теперь вас зовут: %s!\n-100 %s!"%(command, icons['coins'])
							else: text = "Ваше имя слишком длинное!\nВведите ваше новое имя:\n(назад)"
						else: text = "Ваше имя введено не правильно!\nВведите ваше новое имя:\n(назад)"
					else: text = "Кто-то уже использует это имя!\nВведите ваше новое имя:\n(назад)"
			if is_update:
				local = self.core.assoc(data['location'])
				if local in self.core.location._list: keyboard = self.core.location.keyboard(local)
				if local == 'character': 
					text, c_armor = "Персонаж (%s):\n\nУровень: %r %s\n%s: %r/5 %s: %r/%r %s: %s\n\n"%(data['vk_name'], data['level'], ["(%s: %r/%r %s: %r)"%(icons['xp'], data['xp'], self.level(data['level']), '&#128302;', data['rating']), "(%s: %r %s: %r)"%(icons['xp'], data['xp'], '&#128302;', data['rating'])][data['level'] >= 20], icons['health'], data['hp'], icons['energy'], math.floor(data['energy']), 5 * (2 - int(not 'энергохранилище' in data['upgrade'])), icons['coins'], self.core.translate.number(data['coins'])), (self.core.stats(data=data['armor']))
					for row in ['head', 'body', 'weapon']:
						if row in data['armor']:
							item = self.core.item(data['armor'][row])
							if item is not None:
								text += item['icon']
								if row == 'head': text = text + '\n&#128102;\n'
						else:
							if row == 'head': text += '&#128102;\n'
							elif row == 'body': text += '&#128085;'
					text += "\n&#128094;&#128094;\n\nДоп. шанс &#9876; атаки: %r\nДоп. шанс &#128737; защиты: %r\n\n&#128215; Улучшения: "%(c_armor[1], c_armor[0])
					if len(data['upgrade']):
						arr = []
						for i in range(0, len(data['upgrade'])):
							item = self.core.item(data['upgrade'][i])
							if item is not None: arr.append("%s %s"%(item['icon'], item['name']))
						text += ', '.join(arr)
					else: text += "нет"
					text += "\n(инвентарь, мастерская, сменить имя, назад)"
				elif local == 'map': 
					text, count = "&#128220; Карта:\n\n", 0
					for row in sorted(Travel, key=lambda i: Travel[i]['time']):
						timer = (Travel[row]['time'] * (1 - .5 * int('лошадь' in data['upgrade'])))
						text += "%s %s: %s"%(Travel[row]['icon'], Travel[row]['name'], ["нужен %r уровень!\n"%Travel[row]['level'], "нужно %r %s"%(Travel[row]['energy'], icons['energy'])][data['level'] >= Travel[row]['level']])
						if Travel[row]['need'] is not None: # нужные предметы:
							for key in Travel[row]['need']:
								item = self.core.item(key)
								text += ", %s %s"%(item['icon'], item['name'])
						if data['level'] >= Travel[row]['level']: text += " %s: %s\n"%(icons['time'], self.core.time(timer, is_time=False))
						if count < 2: count += 1
						else:
							text += '\n'
							count = 0
					text += "\n\nЗапас %s энергии: %r/%r\n(<локация>, назад)"%(icons['energy'], math.floor(data['energy']), 5 * (1 + int('энергохранилище' in data['upgrade'])))
				elif local == 'inventory': 
					text = "&#127890; Инвентарь:\n\n"
					if len(data['inv']):
						arr = []
						for row in sorted(data['inv'], key=lambda i: data['inv'][i], reverse=True):
							item = self.core.item(row)
							if item is not None:
								if data['inv'][row] > 0: arr.append("%r шт. %s %s"%(data['inv'][row], item['icon'], item['name']))
						text += ', '.join(arr) + "\n"
					else: text += "Пусто!\n"
					text += "\n(использовать <предмет>, продать <кол-во> <предмет> <сумма>, назад)"
				elif local == 'fight': 
					text, self.core.location._list[local]['keyboard'], self.core.location._list['commands'] = self.local.fight(data)
					keyboard = self.core.location.keyboard(local)
				elif local == 'dialog': 
					if data['location'] & assoc['player']: text = "Начать сражение?\n(да, нет)"
					elif (data['location'] & assoc['traid']) and not (data['location'] & assoc['character']): 
						text = self.local.dialog(numb=data['messages'], user_id=user_id)
					else: text = self.local.dialog(nickname=1)
				elif local == 'craft': text = self.local.craft(inv=data['inv'])
				elif local == 'tavern': 
					_list = ['&#9749;', '&#127789;', '&#129365;', '&#129363;', '&#127871;', '&#127866;', '&#127854;', '&#127850;', '&#127847;']
					text, users, messages = "%s Таверна!\nОнлайн: "%_list[random.randint(0, len(_list) - 1)], [], []
					for row in self.core.query.many("SELECT * FROM `tavern`"): users.append(row[1])
					if len(users): text += ', '.join(users)
					else: text += "никого нет"
					for row in self.core.query.many("SELECT * FROM `mail` WHERE `user_id`=%s"%user_id): messages.append("от %s: %s"%(row[2], row[1]))
					if len(messages): text += "\n\nБармен передает вам сообщения:\n%s"%'\n'.join(messages)
					text += "\n\n(бармен, назад)"
					commands.append("DELETE FROM `mail` WHERE `user_id`=%s"%str(user_id))
				elif local == 'nickname': text = "Введите ваше новое имя:\n(назад чтобы выйти)"
				elif local == 'traid': text, keyboard = self.local.traid(user_id=user_id, page=0), self.core.location.keyboard(local)
				elif local in Travel.keys():
					if data['is_travel'] - time.time() < 0 and not ('name' in data['enemy']): 
						data['location'], is_keyboard, obj = 0, 1, self.finish(data=data, user_id=user_id)
						if obj is not None: text, keyboard = obj
						else: is_keyboard = 0
					else: text, is_keyboard = "Осталось %s: %s"%(icons['time'], self.core.time(data['is_travel'])), 0
				elif local == 'player': text = "&#9876; Арена!\nВ очереди: %r &#128100;\nОжидайте вашей очереди!\n\n(назад)"%(int(self.core.query.one("SELECT COUNT(*) FROM `arena`")[0]) - 1) # арена.
				elif local == 'city': # главный экран:
					text, c_time, find = "Лагерь исследователей:\n&#127795;&#127795;&#127795;...&#127969;.....&#127972;...&#127755;&#127980;...&#127795;&#127795;&#127795;\n\n", datetime.datetime.today(), False
					text += "&#128195; Ежедневные квесты: (%s)\n"%(self.core.time(time.time() + (24 * 3600 - (c_time.hour * 3600 + c_time.minute * 60)) + 1))
					for row in self.core.world.many("SELECT * FROM `quests` WHERE `active`=1"):
						quest, is_finish, find = self.core.quest(row), False, True
						text += quest['name'] + " ("
						for key in quest['need']:
							if quest['users'] is not None:
								if str(user_id) in quest['users']:
									if quest['users'][str(user_id)] >= quest['need'][key]:
										text += "выполнено!)"
										is_finish = True
									else: text += "%r/%r"%(quest['users'][str(user_id)], quest['need'][key])
								else: text += "0/%r"%quest['need'][key]
							else: text += "0/%r"%quest['need'][key]
						if not is_finish:
							text += ") награда:\n"
							if quest['price'] is not None:
								for val in quest['price']:
									if val == 'xp' or val == 'coins': text += "%r %s "%(quest['price'][val], icons[val])
									else:
										item = self.core.item(val)
										if item is not None: text += "%r %s %s "%(quest['price'][val], item['icon'], item['name'])
						text += '\n'
					if not find: text += "Пока ничего нет!\n"
					text += "\n(персонаж, карта, таверна, рынок, арена)"
			commands.append("UPDATE `users` SET `location`=%r WHERE `username`=%s"%(data['location'], user_id))
		else: # новый пользователь:
			text = self.add_user(user_id)
			keyboard.add_button('Начать!', color='positive')
		if is_message: # отправка сообщения игроку:
			if not is_keyboard: keyboard = None
			else: keyboard = keyboard.get_keyboard()
			self.core.send(user_id=user_id, message=text, keyboard=keyboard)
	def timer(self): # таймер:
		try:
			for user in self.core.query.many("SELECT * FROM `users`"):
				arr, data = [], self.core.player(user)
				if 'username' in data['is_arena']:
					if (data['messages'] - time.time()) < 0:
						arena_user, keys = self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%data['is_arena']['username'])), VkKeyboard(one_time=True)
						if arena_user is not None:
							keys.add_button('Назад', color='primary')
							arena_user['location'] = 0
							self.core.send(user_id=data['is_arena']['username'], message="Время запроса истекло!\n(назад)", keyboard=keys.get_keyboard())
							self.core.send(user_id=data['id'], message="Время запроса истекло!\n(назад)", keyboard=keys.get_keyboard())
							commands.append("UPDATE `users` SET `is_arena`='{}',`location`=%r,`enemy`='{}',`messages`=0,`hp`=5 WHERE `username`=%s"%(arena_user['location'], data['is_arena']['username']))
						commands.append("UPDATE `users` SET `is_arena`='{}',`location`=%r,`enemy`='{}',`messages`=0,`hp`=5 WHERE `username`=%s"%(arena_user['location'], user[0]))
						self.clear()
				else: # восстановление здоровья и энергии:
					if not data['is_travel']:
						if data['hp'] > 0:
							if (data['hp'] < 5) and (datetime.datetime.today().minute in [0, 30]):
								if (data['hp'] + 1) == 5: self.core.send(user_id=user[0], message="%s Здоровье восстановлено!"%icons['health'])
								arr.append("`hp`=%r"%(data['hp'] + 1))
							_max = 5 * (2 - int(not 'энергохранилище' in data['upgrade']))
							if data['energy'] < _max:
								if data['energy'] + .2 >= _max: self.core.send(user_id=user[0], message="%s Энергия восстановлена!"%icons['energy'])
								arr.append("`energy`=%r"%min(data['energy'] + .2, _max))
								print(data['id'], data['energy'])
						elif (data['messages'] - time.time()) <= 0:
							self.core.send(user_id=user[0], message="%s Здоровье восстановлено!"%icons['health'])
							arr.append("`hp`=5")
					else: # события во время походов:
						if not 'name' in data['enemy']:
							timer, local = data['is_travel'] - time.time(), self.core.assoc(data['location'])
							if timer > 0:
								if local in Travel:
									t_time, keys, point = Travel[local]['time'] * (1 - .5 * int('лошадь' in data['upgrade'])), VkKeyboard(one_time=True), []
									keys.add_button('Атака', color='positive');
									keys.add_button('Защита', color='default');
									if data['level'] < 5 or data['level'] >= 15: point.append(t_time * .5)
									if data['level'] >= 5:
										point.append(t_time * .25)
										point.append(t_time * .75)
									for row in point:
										if ((timer - row) / 60) <= 1 and ((timer - row) / 60) >= 0:
											for nrow in self.core.world.many("SELECT * FROM `enemy` WHERE `location`='%s' AND `level`<=%r"%(local, data['level'])):
												enemy, c_armor = self.core.enemy(nrow), (self.core.stats(data=data['armor']))
												if enemy is not None:
													if self.change(enemy['change']):
														data['location'] |= assoc['fight']
														arr.append("`enemy`='%s',`is_travel`=%r,`location`=%r,`messages`=%r"%(json.dumps({'name': enemy['name']}), timer, data['location'], time.time() + 300))
														self.core.send(user_id=user[0], message="На вас напал %s %s!\n\nШанс &#9876; атаки: %r\nШанс &#128737; защиты: %r\n\n(атака, защита)"%(enemy['icon'], enemy['name'], enemy['damage_change'] + c_armor[1], enemy['leave_change'] + c_armor[0]), keyboard=keys.get_keyboard())
													break
								else:
									self.core.gui.add_error(text='error location!')
									arr.append('`is_travel`=0')
							else: # завершение похода:
								obj = self.finish(user_id=user[0], data=data)
								arr.append("`location`=0,`is_travel`=0")
								if obj is not None: self.core.send(user_id=user[0], message=obj[0], keyboard=obj[1].get_keyboard())
						else: # автоход:
							if data['messages'] - time.time() <= 0:
								enemy, keys = self.core.enemy(self.core.world.one("SELECT * FROM `enemy` WHERE `name`='%s'"%data['enemy']['name'])), VkKeyboard(one_time=True)
								if enemy is not None:
									change = self.change(enemy['leave_change'] + self.core.stats(data=data['armor'])[0])
									dialogs, n_arr = self.core.find(name='default_%r_'%int(change), folder='timeout'), []
									if len(dialogs): text = self.core.read(dialogs[random.randint(0, len(dialogs) - 1)])%(enemy['icon'], enemy['name'])
									if change:
										for row in enemy['price']:
											if row in ['coins', 'xp']:
												data[row] += enemy['price'][row]
												n_arr.append("+%r %s"%(enemy['price'][row], icons[row]))
										text += "\nНаграда: %s"%', '.join(n_arr)
									else: 
										data['hp'] -= 1
										text += "\n%r/5 %s"%(data['hp'], icons['health'])
									if data['hp'] > 0:
										data['location'] &=~ assoc['fight']
										text += "\nОсталось %s: %s"%(icons['time'], self.core.time(time.time() + data['is_travel']))
										self.core.send(user_id=user[0], message=text, keyboard=keys.get_empty_keyboard())
										commands.append("UPDATE `users` SET `location`=%r,`enemy`='{}',`is_travel`=%r,`coins`=%r,`xp`=%r,`hp`=%r WHERE `username`=%s"%(data['location'], time.time() + data['is_travel'], data['coins'], data['xp'], data['hp'], user[0]))
									else:
										keys.add_button('Назад', color='primary')
										commands.append("UPDATE `users` SET `location`=0,`hp`=0,`enemy`='{}',`messages`=%r,`is_travel`=0 WHERE `username`=%s"%(time.time() + 3600, user[0]))
										self.core.send(user_id=user[0], message="%s Вы были сильно ранены!\nВас принесли в лагерь!\n(назад)"%icons['health'], keyboard=keys.get_keyboard())
					if len(arr): commands.append("UPDATE `users` SET %s WHERE `username`=%s"%(','.join(arr), user[0]))
			timer = datetime.datetime.today()
			if self.core.hour != timer.hour:
				if timer.weekday() != self.core.day: # обновление квестов:
					self.core.change_quests()
					self.core.day = timer.weekday()
				for row in self.core.query.many("SELECT * FROM `tavern`"): # таверна:
					user = self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%row[0]))
					if user is not None:
						self.quest(value='tavern', data=user, user_id=row[0], save=True)
						if timer.weekday() in [5, 6]: # выходной опыт:
							user['xp'] += 1
							user, levelup = self.up(data=user)
							if levelup is not None: self.core.send(user_id=row[0], message=levelup)
							commands.append("UPDATE `users` SET `xp`=%r,`level`=%r,`hp`=%r,`energy`=%r,`coins`=%r WHERE `username`=%s"%(user['xp'], user['level'], user['hp'], user['energy'], user['coins'], row[0]))
				if timer.hour == 21 and self.core.day == 4: # розыгрыш наград среди лидеров арены:
					_sum, arr, text = int(self.core.world.one("SELECT `coins` FROM `world`")[0] * .25), [], "В конце недели лидеры арены получают награды!\nПобедители:\n\n"
					for i in self.core.table():
						user = self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%i['id']))
						if user is not None:
							self.core.query.save("UPDATE `users` SET `coins`=%r WHERE `username`=%s"%(user['coins'] + math.floor(_sum * .5), user['id']))
							self.core.send(user_id=user['id'], message="Вы получили: +%r %s!"%(math.floor(_sum * .5), icons['coins']))
							arr.append("%r. %s (%s: %r) выиграл %r %s!"%(len(arr) + 1, user['vk_name'], icons['rating'], user['rating'], math.floor(_sum * .5), icons['coins']))
							self.core.tax(-math.floor(_sum * .5))
							_sum -= math.floor(_sum * .5)
					text += '\n'.join(arr)
					self.core.session.wall.post(owner_id=-self.core.group_id, from_group=1, attachment="photo-173231254_456239071", message=text)
					self.core.table()
				else: self.core.table()
				self.core.hour = timer.hour
			if self.core.query.one("SELECT COUNT(*) FROM `arena`")[0] > 1: # арена:
				arena, keys = {0: {}, 1: {}}, VkKeyboard(one_time=True)
				for i in range(0, 2):
					data = self.core.player(self.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%self.core.query.one("SELECT `username` FROM `arena` LIMIT 1 OFFSET %r"%i)[0]))
					if data:
						arena[1 - i]['is_arena'] = {'username': data['id'], 'vk_name': data['vk_name']}
						arena[1 - i]['messages'], arena[i]['username'], arena[i]['location'] = time.time() + 180, data['id'], data['location']
						arena[i]['location'] |= assoc['dialog']
						commands.append("DELETE FROM `arena` LIMIT 1")
				keys.add_button('Да', color='positive')
				keys.add_button('Нет', color='negative')
				for i in range(0, 2):
					user, message = arena[i]['username'], "&#9876; %s хочет сразиться с вами!\nСогласиться?\n\n(да, нет)"%arena[i]['is_arena']['vk_name']
					commands.append("UPDATE `users` SET `is_arena`='%s',`messages`=%r,`location`=%r WHERE `username`=%s"%(json.dumps(arena[i]['is_arena']), arena[i]['messages'], arena[i]['location'], user))
					self.core.send(user_id=user, message=message, keyboard=keys.get_keyboard())
		except requests.ConnectionError:
			self.core.gui.add_error(text='connection error')
			self.resend()
		except requests.ReadTimeout: self.core.gui.add_error(time='timeout')
		except Exception as error: print(error)
		finally:
			self.clear()
			threading.Timer(60, self.timer).start()
	def resend(self):
		for user in self.core.vk.method('messages.getConversations', {'group_id':self.core.group_id, 'filter': 'unread'})['items']:
			self.update(command=user['last_message']['text'], user_id=user['last_message']['from_id'])

game = Game(Core(token=token, login=login, password=password, group_id=173231254))
game.core.table()
threading.Timer(60 - datetime.datetime.today().second, game.timer).start()
longpoll = VkBotLongPoll(game.core.vk, game.core.group_id, wait=30)
game.resend()
game.core.gui.render()
while True:
	try:
		for event in longpoll.listen():
			if event.type == VkBotEventType.MESSAGE_NEW: game.update(command=event.obj.text, user_id=str(event.obj.from_id))
			elif event.type == VkBotEventType.GROUP_JOIN:
				obj = game.core.player(game.core.query.one("SELECT * FROM `users` WHERE `username`=%s"%str(event.obj.user_id)))
				if obj is not None:
					if not obj['is_price']:
						game.core.send(user_id=event.obj.user_id, message="Большое спасибо за подписку!\nВаш %s бонус: +20 %s!"%(icons['price'], icons['coins']))
						commands.append("UPDATE `users` SET `is_price`=1,`coins`=%r WHERE `username`=%s"%(obj['coins'] + 20, str(event.obj.user_id)))
			game.clear()
	except requests.ConnectionError:
		game.core.gui.add_error(text='connection error')
		game.resend()
	except requests.ReadTimeout:
		game.core.gui.add_error(text='timeout')
	except Exception as error: print(error)
game.core.query.close()
game.core.world.close()