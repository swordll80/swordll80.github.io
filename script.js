(function () {
  'use strict';

  var STORAGE_KEY = 'swordll80.sidebarCollapsed';
  var MOBILE_QUERY = window.matchMedia('(max-width: 768px)');
  var navData = [
    { title: '简介', children: [
      { title: '首页', target: 'intro-home' },
      { title: '关于本站', target: 'intro-about' },
      { title: '项目方向', target: 'intro-projects' }
    ]},
    { title: '工具', children: [
      { title: '工具总览', target: 'tools-overview' },
      { title: 'GIS 与 KML', target: 'tools-gis' },
      { title: '数据结构工具', target: 'tools-data' },
      { title: 'Web 小工具', target: 'tools-web' }
    ]},
    { title: '学习', children: [
      { title: '学习总览', target: 'learn-overview' },
      { title: '编程笔记', target: 'learn-programming' },
      { title: 'C/C++ 工程实践', target: 'learn-engineering' }
    ]},
    { title: '户外', children: [
      { title: '地图与轨迹', target: 'outdoor-map' }
    ]}
  ];

  var navTree = document.getElementById('navTree');
  var sidebarToggle = document.getElementById('sidebarToggle');
  var edgeHotspot = document.getElementById('edgeHotspot');
  var drawerBackdrop = document.getElementById('drawerBackdrop');
  var sidebar = document.getElementById('sidebar');
  var content = document.getElementById('content');
  var peekTimer = 0;

  function isMobile() {
    return MOBILE_QUERY.matches;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function renderNav() {
    navTree.innerHTML = '';
    navData.forEach(function (group) {
      var groupNode = el('div', 'nav-group open');
      var titleBtn = el('button', 'nav-title');
      titleBtn.type = 'button';
      titleBtn.innerHTML = '<span class="arrow">▶</span><strong>' + group.title + '</strong>';
      var children = el('div', 'nav-children');
      group.children.forEach(function (item) {
        var link = el('a', 'nav-link', item.title);
        link.href = '#' + item.target;
        link.setAttribute('data-nav-link', '');
        link.setAttribute('data-target', item.target);
        children.appendChild(link);
      });
      titleBtn.addEventListener('click', function () {
        groupNode.classList.toggle('open');
      });
      groupNode.appendChild(titleBtn);
      groupNode.appendChild(children);
      navTree.appendChild(groupNode);
    });
  }

  function setCollapsed(collapsed, save) {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    document.body.classList.remove('sidebar-peek');
    sidebarToggle.setAttribute('aria-expanded', String(!collapsed));

    /* 手机端目录是抽屉，不保存状态，避免下次打开页面被侧栏遮住。 */
    if (save && !isMobile()) {
      localStorage.setItem(STORAGE_KEY, collapsed ? 'true' : 'false');
    }
  }

  function initSidebarState() {
    if (isMobile()) {
      setCollapsed(true, false);
      return;
    }

    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved === null) {
      setCollapsed(false, false);
    } else {
      setCollapsed(saved === 'true', false);
    }
  }

  function activate(targetId) {
    var target = document.getElementById(targetId) || document.getElementById('intro-home');

    Array.prototype.forEach.call(document.querySelectorAll('.content-section'), function (section) {
      section.classList.toggle('active', section === target);
    });

    Array.prototype.forEach.call(document.querySelectorAll('.nav-link'), function (link) {
      link.classList.toggle('active', link.getAttribute('data-target') === target.id);
    });

    document.title = (target.dataset.title || '首页') + ' · swordll80.github.io';

    if (content && content.focus) {
      try {
        content.focus({ preventScroll: true });
      } catch (e) {
        content.focus();
      }
    }

    if (isMobile()) {
      setCollapsed(true, false);
      window.scrollTo(0, 0);
    }
  }

  function handleHash() {
    var id = location.hash ? decodeURIComponent(location.hash.slice(1)) : 'intro-home';
    activate(id);
  }

  renderNav();
  initSidebarState();
  handleHash();

  sidebarToggle.addEventListener('click', function () {
    setCollapsed(!document.body.classList.contains('sidebar-collapsed'), true);
  });

  if (drawerBackdrop) {
    drawerBackdrop.addEventListener('click', function () {
      setCollapsed(true, false);
    });
  }

  document.addEventListener('click', function (event) {
    var link = event.target.closest ? event.target.closest('[data-nav-link]') : null;
    if (!link) return;
    var hash = link.getAttribute('href');
    if (!hash || hash.charAt(0) !== '#') return;
    event.preventDefault();
    history.pushState(null, '', hash);
    handleHash();
  });

  window.addEventListener('hashchange', handleHash);

  if (edgeHotspot) {
    edgeHotspot.addEventListener('mouseenter', function () {
      if (!isMobile() && document.body.classList.contains('sidebar-collapsed')) {
        document.body.classList.add('sidebar-peek');
      }
    });

    edgeHotspot.addEventListener('click', function () {
      if (!isMobile() && document.body.classList.contains('sidebar-collapsed')) {
        document.body.classList.add('sidebar-peek');
      }
    });
  }

  if (sidebar) {
    sidebar.addEventListener('mouseleave', function () {
      if (!isMobile() && document.body.classList.contains('sidebar-collapsed')) {
        clearTimeout(peekTimer);
        peekTimer = setTimeout(function () {
          document.body.classList.remove('sidebar-peek');
        }, 160);
      }
    });
  }

  function handleMobileQueryChange() {
    initSidebarState();
  }

  if (MOBILE_QUERY.addEventListener) {
    MOBILE_QUERY.addEventListener('change', handleMobileQueryChange);
  } else if (MOBILE_QUERY.addListener) {
    MOBILE_QUERY.addListener(handleMobileQueryChange);
  }
})();
