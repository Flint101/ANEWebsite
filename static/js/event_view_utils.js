function roster_list_db_to_object(roster_list){
    /*
    // Rework the roster information we get from the DB into a more managable format
    */
    let roster_chars = []
    for (let i in roster_list) {
        let wishes = unpackWishes(roster[i].wishes)
        let roles = ROLES_PER_CLASS[roster[i].playable_class]
        roster_chars.push({
            'name': roster[i].name,
            'playable_class': roster[i].playable_class,
            'roles': roles,
            'account_id': roster[i].account_id,
            'wishes': wishes,
        })
    }
    return roster_chars
}

function unpackWishes(wishesDb) {
    // 0 Refers to first object, there will only ever be 1
    parsedWishes = JSON.parse(wishesDb)[0]
    if(parsedWishes) {
        wishes = parsedWishes.fields.wishes
        return wishes
    }
    return []
}

function boss_list_db_to_object(boss_list){
    /*
    // Rework the boss information we get from the DB into a more managable format
    */
    let bosses = {}
    boss_list.forEach(boss => {
        boss = boss.fields
        bosses[boss.boss_id]={
            'name': boss.boss_name,
            'id':boss.boss_id,
        }
    })
    return bosses
}

function is_user_selected_for_boss(boss_id){
    if(typeof(user_event_summary[boss_id]) !== "undefined"){
        if(typeof(user_event_summary[boss_id].name) !== "undefined"){
            return true
        }
        return false
    }
    return false
}

function char_moved_ajax(char_name, role, current_boss_id){
    $.ajax({
        url: window.location.href,
        data: {
            'name': char_name,
            'role': role,
            'boss_id': current_boss_id,
        },
        dataType: 'json',
        timeout: 1000,
    })
}

function is_char_selected_for_boss(boss_id, char_name){
    let boss_roster = boss_rosters[boss_id]
    for(let role in boss_roster){
        if(boss_roster[role].includes(char_name)){
            return true
        }
    }
    return false
}

// Rework this function. Very inefficient to get the roster list every time.
function get_playable_class_by_char_name(char_name){
    let roster_list = roster_list_db_to_object(roster)
    for(let i in roster_list){
        let char = roster_list[i]
        if(char.name == char_name){
            return char.playable_class
        }
    }
    return 'Character not in roster'
}

// reset when leaving event view page
function setLastVisitedBossView(view){
    sessionStorage.setItem('lastVisitedBossView', view)
}
function loadBossViewFromSessionStorage(){
    const lastVisitedBossView = eval(sessionStorage.getItem('lastVisitedBossView'))
    if(lastVisitedBossView != null){
        changeBossView(lastVisitedBossView)
    }
}
$(document).ready(()=>{
    if(is_staff) loadBossViewFromSessionStorage()
})

function groupBy(array, key){
    return array.reduce((group, element) => {
        const keyValue = element[key]
        return { ...group, [keyValue]: [...(group[keyValue] ?? []),
        element] }
    }, {})
}

function removeValueFromArray(arr, value){
    var index = arr.indexOf(value);
    if (index > -1) {
      arr.splice(index, 1);
    }
    return arr;
}

function sortByWishes(roster, bossId) {
    // TODO - returned list so that 0 sorted at end, then 99, then rest in order. 
    let sortedRoster = roster.map((char) => {
        let wish = char.wishes[bossId]
        if(wish == undefined) {
            wish = '-'
        }
        return {
            'name': char.name,
            'playable_class': char.playable_class,
            'roles': char.roles,
            'account_id': char.account_id,
            'wishes': char.wishes,
            'wish': char.wishes[bossId] != undefined ? char.wishes[bossId] : '-',
         }
    })
    return groupBy(sortedRoster, "wish")
}