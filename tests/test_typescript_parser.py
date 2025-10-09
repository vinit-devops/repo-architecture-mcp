"""Tests for the TypeScript parser."""

import pytest
from repo_architecture_mcp.parsers.typescript_parser import TypeScriptParser
from repo_architecture_mcp.models import Visibility


class TestTypeScriptParser:
    """Test cases for the TypeScript parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = TypeScriptParser()
    
    def test_supported_extensions(self):
        """Test supported file extensions."""
        assert self.parser.supported_extensions == ['.ts', '.tsx']
    
    def test_language_name(self):
        """Test language name."""
        assert self.parser.language_name == 'typescript'
    
    @pytest.mark.asyncio
    async def test_parse_interfaces(self):
        """Test parsing interface definitions."""
        code = '''
interface User {
    name: string;
    age: number;
    email?: string;
}

interface Admin extends User {
    permissions: string[];
    isActive: boolean;
}

interface MultipleExtends extends User, Admin {
    role: string;
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        # Interfaces are treated as classes
        assert len(result.classes) == 3
        
        user_interface = next(cls for cls in result.classes if cls.name == 'User')
        assert len(user_interface.attributes) == 3
        
        admin_interface = next(cls for cls in result.classes if cls.name == 'Admin')
        assert admin_interface.inheritance == ['User']
        
        multiple_interface = next(cls for cls in result.classes if cls.name == 'MultipleExtends')
        assert set(multiple_interface.inheritance) == {'User', 'Admin'}
    
    @pytest.mark.asyncio
    async def test_parse_classes_with_access_modifiers(self):
        """Test parsing classes with TypeScript access modifiers."""
        code = '''
class AccessModifierClass {
    public publicProp: string;
    private privateProp: number;
    protected protectedProp: boolean;
    readonly readonlyProp: string = "readonly";
    static staticProp: number = 42;
    
    constructor(public name: string, private age: number) {}
    
    public publicMethod(): void {}
    private privateMethod(): string { return ""; }
    protected protectedMethod(): number { return 0; }
    static staticMethod(): void {}
    abstract abstractMethod(): void;
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        cls = result.classes[0]
        
        # Check properties
        props = {prop.name: prop for prop in cls.attributes}
        assert props['publicProp'].visibility == Visibility.PUBLIC
        assert props['privateProp'].visibility == Visibility.PRIVATE
        assert props['protectedProp'].visibility == Visibility.PROTECTED
        assert props['staticProp'].is_static is True
        
        # Check methods
        methods = {method.name: method for method in cls.methods}
        assert methods['publicMethod'].visibility == Visibility.PUBLIC
        assert methods['privateMethod'].visibility == Visibility.PRIVATE
        assert methods['protectedMethod'].visibility == Visibility.PROTECTED
        assert methods['staticMethod'].is_static is True
        assert methods['abstractMethod'].is_abstract is True
    
    @pytest.mark.asyncio
    async def test_parse_generic_types(self):
        """Test parsing generic types and functions."""
        code = '''
interface Container<T> {
    value: T;
    getValue(): T;
}

class GenericClass<T, U> {
    private items: T[] = [];
    
    add(item: T): void {
        this.items.push(item);
    }
    
    transform<V>(fn: (item: T) => V): V[] {
        return this.items.map(fn);
    }
}

function identity<T>(arg: T): T {
    return arg;
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        # Should parse without errors
        assert len(result.classes) == 2  # Interface + Class
        assert len(result.functions) >= 1
        
        generic_class = next(cls for cls in result.classes if cls.name == 'GenericClass')
        assert len(generic_class.methods) >= 2
    
    @pytest.mark.asyncio
    async def test_parse_type_annotations(self):
        """Test parsing TypeScript type annotations."""
        code = '''
function typedFunction(
    name: string,
    age: number = 25,
    hobbies: string[],
    metadata?: Record<string, any>
): Promise<User> {
    return Promise.resolve({ name, age, hobbies });
}

class TypedClass {
    private users: Map<string, User> = new Map();
    
    async getUser(id: string): Promise<User | null> {
        return this.users.get(id) || null;
    }
    
    setUser(id: string, user: User): void {
        this.users.set(id, user);
    }
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        # Check function type annotations
        func = result.functions[0]
        assert func.return_type == 'Promise<User>'
        
        params = {p.name: p for p in func.parameters}
        assert params['name'].type_hint == 'string'
        assert params['age'].type_hint == 'number'
        assert params['age'].default_value == '25'
        assert params['hobbies'].type_hint == 'string[]'
        assert params['metadata'].type_hint == 'Record<string, any>'
        
        # Check method type annotations
        cls = result.classes[0]
        get_user_method = next(m for m in cls.methods if m.name == 'getUser')
        assert get_user_method.return_type == 'Promise<User | null>'
        
        set_user_method = next(m for m in cls.methods if m.name == 'setUser')
        assert set_user_method.return_type == 'void'
    
    @pytest.mark.asyncio
    async def test_parse_enums(self):
        """Test parsing enum definitions."""
        code = '''
enum Color {
    Red,
    Green,
    Blue
}

enum Status {
    Active = "active",
    Inactive = "inactive",
    Pending = "pending"
}

enum HttpStatus {
    OK = 200,
    NotFound = 404,
    ServerError = 500
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        # Enums might be parsed as classes or handled separately
        # The exact implementation depends on the parser
        assert result.language == 'typescript'
    
    @pytest.mark.asyncio
    async def test_parse_abstract_classes(self):
        """Test parsing abstract classes."""
        code = '''
abstract class AbstractShape {
    protected name: string;
    
    constructor(name: string) {
        this.name = name;
    }
    
    abstract getArea(): number;
    abstract getPerimeter(): number;
    
    getName(): string {
        return this.name;
    }
}

class Circle extends AbstractShape {
    private radius: number;
    
    constructor(radius: number) {
        super("Circle");
        this.radius = radius;
    }
    
    getArea(): number {
        return Math.PI * this.radius * this.radius;
    }
    
    getPerimeter(): number {
        return 2 * Math.PI * this.radius;
    }
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        assert len(result.classes) == 2
        
        abstract_class = next(cls for cls in result.classes if cls.name == 'AbstractShape')
        assert abstract_class.is_abstract is True
        
        circle_class = next(cls for cls in result.classes if cls.name == 'Circle')
        assert circle_class.inheritance == ['AbstractShape']
        assert circle_class.is_abstract is False
    
    @pytest.mark.asyncio
    async def test_parse_implements_clause(self):
        """Test parsing classes that implement interfaces."""
        code = '''
interface Flyable {
    fly(): void;
}

interface Swimmable {
    swim(): void;
}

class Duck implements Flyable, Swimmable {
    fly(): void {
        console.log("Duck is flying");
    }
    
    swim(): void {
        console.log("Duck is swimming");
    }
}

class Airplane implements Flyable {
    fly(): void {
        console.log("Airplane is flying");
    }
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        duck_class = next(cls for cls in result.classes if cls.name == 'Duck')
        assert set(duck_class.interfaces) == {'Flyable', 'Swimmable'}
        
        airplane_class = next(cls for cls in result.classes if cls.name == 'Airplane')
        assert airplane_class.interfaces == ['Flyable']
    
    @pytest.mark.asyncio
    async def test_parse_decorators(self):
        """Test parsing TypeScript decorators."""
        code = '''
@Component({
    selector: 'app-user',
    template: '<div>User</div>'
})
class UserComponent {
    @Input() name: string;
    @Output() nameChange = new EventEmitter<string>();
    
    @HostListener('click', ['$event'])
    onClick(event: Event): void {}
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        cls = result.classes[0]
        assert len(cls.decorators) > 0
        
        # Check method decorators
        click_method = next(m for m in cls.methods if m.name == 'onClick')
        assert len(click_method.decorators) > 0
    
    @pytest.mark.asyncio
    async def test_parse_namespace(self):
        """Test parsing TypeScript namespaces."""
        code = '''
namespace Utils {
    export function formatDate(date: Date): string {
        return date.toISOString();
    }
    
    export class Logger {
        static log(message: string): void {
            console.log(message);
        }
    }
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        # Namespaces might be handled as classes or separately
        assert result.language == 'typescript'
    
    @pytest.mark.asyncio
    async def test_parse_union_and_intersection_types(self):
        """Test parsing union and intersection types."""
        code = '''
type StringOrNumber = string | number;
type UserWithTimestamp = User & { timestamp: Date };

function process(value: string | number | boolean): void {}

class Handler {
    handle(data: User & Admin): void {}
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        # Should parse without errors
        assert result.language == 'typescript'
        assert len(result.functions) >= 1
        assert len(result.classes) >= 1
    
    @pytest.mark.asyncio
    async def test_parse_async_await(self):
        """Test parsing async/await patterns."""
        code = '''
class ApiService {
    async fetchUser(id: string): Promise<User> {
        const response = await fetch(`/api/users/${id}`);
        return response.json();
    }
    
    async saveUser(user: User): Promise<void> {
        await fetch('/api/users', {
            method: 'POST',
            body: JSON.stringify(user)
        });
    }
}

async function processUsers(): Promise<User[]> {
    const users = await ApiService.fetchUsers();
    return users.filter(user => user.isActive);
}
'''
        
        result = await self.parser.parse_file('test.ts', code)
        
        cls = result.classes[0]
        fetch_method = next(m for m in cls.methods if m.name == 'fetchUser')
        assert fetch_method.is_async is True
        
        process_func = next(f for f in result.functions if f.name == 'processUsers')
        assert process_func.is_async is True
    
    @pytest.mark.asyncio
    async def test_parse_empty_file(self):
        """Test parsing an empty TypeScript file."""
        result = await self.parser.parse_file('test.ts', '')
        
        assert result.language == 'typescript'
        assert result.classes == []
        assert result.functions == []
        assert result.imports == []
        assert result.exports == []
        assert result.global_variables == []
        assert result.parse_errors == []